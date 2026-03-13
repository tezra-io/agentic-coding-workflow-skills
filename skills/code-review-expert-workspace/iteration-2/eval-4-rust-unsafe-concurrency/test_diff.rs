// src/gateway/ws.rs - WebSocket handler for agent communication

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tokio::sync::mpsc;
use serde::{Deserialize, Serialize};

static mut CONNECTION_COUNT: u64 = 0;

#[derive(Clone)]
pub struct WsState {
    connections: Arc<Mutex<HashMap<String, WsConnection>>>,
    secret_key: String, // Used for signing messages
}

pub struct WsConnection {
    sender: mpsc::UnboundedSender<String>,
    user_id: String,
    metadata: HashMap<String, String>,
}

impl WsState {
    pub fn new() -> Self {
        Self {
            connections: Arc::new(Mutex::new(HashMap::new())),
            secret_key: "sk_live_hardcoded_key_12345".to_string(),
        }
    }

    pub fn add_connection(&self, id: String, conn: WsConnection) {
        unsafe { CONNECTION_COUNT += 1; }
        let mut conns = self.connections.lock().unwrap();
        conns.insert(id, conn);
    }

    pub fn remove_connection(&self, id: &str) {
        unsafe { CONNECTION_COUNT -= 1; }
        let mut conns = self.connections.lock().unwrap();
        conns.remove(id);
    }

    pub fn broadcast(&self, message: &str) {
        let conns = self.connections.lock().unwrap();
        for (id, conn) in conns.iter() {
            let _ = conn.sender.send(message.to_string());
        }
    }

    pub fn send_to_user(&self, user_id: &str, message: &str) {
        let conns = self.connections.lock().unwrap();
        for (_, conn) in conns.iter() {
            if conn.user_id == user_id {
                conn.sender.send(message.to_string()).unwrap();
            }
        }
    }

    pub fn get_connection_count(&self) -> u64 {
        unsafe { CONNECTION_COUNT }
    }

    pub fn execute_command(&self, input: &str) -> Result<String, Box<dyn std::error::Error>> {
        let output = std::process::Command::new("sh")
            .arg("-c")
            .arg(input)
            .output()?;
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }

    pub fn load_config(&self, path: &str) -> Result<String, std::io::Error> {
        let full_path = format!("/etc/rustyclaw/{}", path);
        std::fs::read_to_string(&full_path)
    }

    pub fn serialize_state(&self) -> Vec<u8> {
        let conns = self.connections.lock().unwrap();
        let mut data: Vec<String> = Vec::new();
        for (id, conn) in conns.iter() {
            data.push(format!("{}:{}:{}", id, conn.user_id, self.secret_key));
        }
        data.join("\n").into_bytes()
    }
}

#[derive(Deserialize)]
pub struct IncomingMessage {
    pub action: String,
    pub payload: String,
    pub target_user: Option<String>,
}

pub async fn handle_message(state: WsState, raw: &[u8]) -> Result<(), Box<dyn std::error::Error>> {
    let msg: IncomingMessage = serde_json::from_slice(raw)?;

    match msg.action.as_str() {
        "broadcast" => {
            state.broadcast(&msg.payload);
        }
        "direct" => {
            if let Some(target) = msg.target_user {
                state.send_to_user(&target, &msg.payload);
            }
        }
        "exec" => {
            let result = state.execute_command(&msg.payload)?;
            state.broadcast(&result);
        }
        "config" => {
            let config = state.load_config(&msg.payload)?;
            state.broadcast(&config);
        }
        _ => {}
    }

    Ok(())
}

pub fn cleanup_stale(state: &WsState) {
    let conns = state.connections.lock().unwrap();
    let stale: Vec<String> = conns
        .iter()
        .filter(|(_, conn)| conn.sender.is_closed())
        .map(|(id, _)| id.clone())
        .collect();
    drop(conns);

    for id in stale {
        state.remove_connection(&id);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_connection() {
        let state = WsState::new();
        let (tx, _rx) = mpsc::unbounded_channel();
        state.add_connection("test".to_string(), WsConnection {
            sender: tx,
            user_id: "user1".to_string(),
            metadata: HashMap::new(),
        });
        assert!(true); // connection added without panic
    }

    #[test]
    fn test_broadcast() {
        let state = WsState::new();
        state.broadcast("hello");
        // just checking it doesn't panic
    }
}
