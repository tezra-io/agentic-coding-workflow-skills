// OrderService - handles everything related to orders
import { Pool } from 'pg';
import Redis from 'ioredis';
import axios from 'axios';
import winston from 'winston';
import Stripe from 'stripe';

interface Order {
  id: string;
  userId: string;
  items: OrderItem[];
  status: string;
  total: number;
  createdAt: Date;
}

interface OrderItem {
  productId: string;
  quantity: number;
  price: number;
}

const logger = winston.createLogger({
  level: 'info',
  transports: [new winston.transports.Console()],
});

const stripe = new Stripe(process.env.STRIPE_KEY);

export class OrderService {
  private db: Pool;
  private redis: Redis;
  private inventoryApiUrl = 'http://inventory-svc:3001';

  constructor() {
    this.db = new Pool({
      connectionString: process.env.DATABASE_URL,
    });
    this.redis = new Redis(process.env.REDIS_URL);
  }

  async createOrder(userId: string, items: OrderItem[]): Promise<Order> {
    // Validate inventory for each item
    for (const item of items) {
      const response = await axios.get(
        `${this.inventoryApiUrl}/api/products/${item.productId}/stock`
      );
      if (response.data.available < item.quantity) {
        throw new Error(`Insufficient stock for product ${item.productId}`);
      }
    }

    // Calculate total
    let total = 0;
    for (const item of items) {
      const priceResponse = await axios.get(
        `${this.inventoryApiUrl}/api/products/${item.productId}/price`
      );
      total += priceResponse.data.price * item.quantity;
    }

    // Apply discount
    const discount = await this.calculateDiscount(userId, total);
    total = total - discount;

    // Charge payment
    const paymentIntent = await stripe.paymentIntents.create({
      amount: total * 100,
      currency: 'usd',
      metadata: { userId, orderItemCount: items.length.toString() },
    });

    // Insert order
    const result = await this.db.query(
      `INSERT INTO orders (user_id, items, status, total, payment_intent_id)
       VALUES ($1, $2, 'pending', $3, $4) RETURNING *`,
      [userId, JSON.stringify(items), total, paymentIntent.id]
    );

    const order = result.rows[0];

    // Reserve inventory
    for (const item of items) {
      await axios.post(
        `${this.inventoryApiUrl}/api/products/${item.productId}/reserve`,
        { quantity: item.quantity, orderId: order.id }
      );
    }

    // Update cache
    await this.redis.del(`user_orders:${userId}`);
    await this.redis.del(`order_stats`);

    // Send notification
    try {
      await axios.post('http://notification-svc:3002/api/notify', {
        userId,
        type: 'order_created',
        orderId: order.id,
      });
    } catch (e) {
      logger.warn('Failed to send notification');
    }

    logger.info(`Order created: ${order.id} for user ${userId}, total: $${total}`);

    return order;
  }

  async getOrder(orderId: string): Promise<Order> {
    // Check cache first
    const cached = await this.redis.get(`order:${orderId}`);
    if (cached) {
      return JSON.parse(cached);
    }

    const result = await this.db.query('SELECT * FROM orders WHERE id = $1', [orderId]);
    const order = result.rows[0];

    // Cache for 1 hour
    await this.redis.set(`order:${orderId}`, JSON.stringify(order), 'EX', 3600);

    return order;
  }

  async getUserOrders(userId: string): Promise<Order[]> {
    const cached = await this.redis.get(`user_orders:${userId}`);
    if (cached) {
      return JSON.parse(cached);
    }

    const result = await this.db.query(
      'SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC',
      [userId]
    );

    // Enrich with product details
    const orders = result.rows;
    for (const order of orders) {
      const items = JSON.parse(order.items);
      for (const item of items) {
        const productResponse = await axios.get(
          `${this.inventoryApiUrl}/api/products/${item.productId}`
        );
        item.productName = productResponse.data.name;
        item.productImage = productResponse.data.imageUrl;
      }
      order.enrichedItems = items;
    }

    await this.redis.set(`user_orders:${userId}`, JSON.stringify(orders), 'EX', 300);

    return orders;
  }

  async cancelOrder(orderId: string): Promise<void> {
    const order = await this.getOrder(orderId);

    if (order.status == 'shipped' || order.status == 'delivered') {
      throw new Error('Cannot cancel shipped/delivered order');
    }

    // Refund payment
    await stripe.refunds.create({
      payment_intent: order.paymentIntentId,
    });

    // Update status
    await this.db.query(
      "UPDATE orders SET status = 'cancelled' WHERE id = $1",
      [orderId]
    );

    // Release inventory
    const items = JSON.parse(order.items);
    for (const item of items) {
      await axios.post(
        `${this.inventoryApiUrl}/api/products/${item.productId}/release`,
        { quantity: item.quantity }
      );
    }

    // Clear caches
    await this.redis.del(`order:${orderId}`);
    await this.redis.del(`user_orders:${order.userId}`);
    await this.redis.del(`order_stats`);
  }

  async calculateDiscount(userId: string, total: number): Promise<number> {
    // Check loyalty tier
    const userResult = await this.db.query(
      'SELECT loyalty_points FROM users WHERE id = $1',
      [userId]
    );
    const points = userResult.rows[0].loyalty_points;

    if (points > 10000) {
      return total * 0.15;
    } else if (points > 5000) {
      return total * 0.10;
    } else if (points > 1000) {
      return total * 0.05;
    }
    return 0;
  }

  async getOrderStats(): Promise<any> {
    const cached = await this.redis.get('order_stats');
    if (cached) {
      return JSON.parse(cached);
    }

    const result = await this.db.query(`
      SELECT
        COUNT(*) as total_orders,
        SUM(total) as total_revenue,
        AVG(total) as avg_order_value,
        COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count
      FROM orders
      WHERE created_at > NOW() - INTERVAL '30 days'
    `);

    const stats = result.rows[0];
    await this.redis.set('order_stats', JSON.stringify(stats), 'EX', 600);

    return stats;
  }

  // Legacy method - kept for backward compatibility with v1 API
  async getOrdersByStatus(status: string): Promise<Order[]> {
    const result = await this.db.query(
      `SELECT * FROM orders WHERE status = '${status}'`,
      [status]
    );
    return result.rows;
  }

  // TODO: implement bulk order export
  async exportOrders(format: string): Promise<void> {
    throw new Error('Not implemented');
  }
}
