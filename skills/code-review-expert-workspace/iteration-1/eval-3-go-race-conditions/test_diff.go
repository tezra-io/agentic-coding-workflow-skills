package sessionmgr

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

// SessionManager handles user sessions with in-memory storage
type SessionManager struct {
	sessions map[string]*Session
	mu       sync.Mutex
	config   *Config
}

type Session struct {
	ID        string
	UserID    string
	Data      map[string]interface{}
	CreatedAt time.Time
	ExpiresAt time.Time
}

type Config struct {
	MaxSessions    int
	SessionTimeout time.Duration
	StoragePath    string
}

var (
	globalManager *SessionManager
	activeCount   int
)

func NewSessionManager(cfg *Config) *SessionManager {
	globalManager = &SessionManager{
		sessions: make(map[string]*Session),
		config:   cfg,
	}
	go globalManager.cleanupLoop()
	return globalManager
}

func (sm *SessionManager) cleanupLoop() {
	for {
		time.Sleep(1 * time.Minute)
		now := time.Now()
		for id, sess := range sm.sessions {
			if now.After(sess.ExpiresAt) {
				delete(sm.sessions, id)
				activeCount--
			}
		}
	}
}

func (sm *SessionManager) CreateSession(w http.ResponseWriter, r *http.Request) {
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "bad request", 400)
		return
	}

	var req struct {
		UserID string `json:"user_id"`
	}
	json.Unmarshal(body, &req)

	// Check session limit
	if len(sm.sessions) >= sm.config.MaxSessions {
		http.Error(w, "too many sessions", 429)
		return
	}

	sessionID := fmt.Sprintf("sess_%d", time.Now().UnixNano())
	session := &Session{
		ID:        sessionID,
		UserID:    req.UserID,
		Data:      make(map[string]interface{}),
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(sm.config.SessionTimeout),
	}

	sm.sessions[sessionID] = session
	activeCount++

	resp, _ := json.Marshal(map[string]string{"session_id": sessionID})
	w.Header().Set("Content-Type", "application/json")
	w.Write(resp)
}

func (sm *SessionManager) GetSession(w http.ResponseWriter, r *http.Request) {
	sessionID := r.URL.Query().Get("id")

	sm.mu.Lock()
	session, exists := sm.sessions[sessionID]
	sm.mu.Unlock()

	if !exists {
		http.Error(w, "not found", 404)
		return
	}

	// Extend session
	session.ExpiresAt = time.Now().Add(sm.config.SessionTimeout)

	resp, _ := json.Marshal(session)
	w.Header().Set("Content-Type", "application/json")
	w.Write(resp)
}

func (sm *SessionManager) UpdateSession(w http.ResponseWriter, r *http.Request) {
	sessionID := r.URL.Query().Get("id")

	session, exists := sm.sessions[sessionID]
	if !exists {
		http.Error(w, "not found", 404)
		return
	}

	body, _ := ioutil.ReadAll(r.Body)
	var updates map[string]interface{}
	json.Unmarshal(body, &updates)

	for k, v := range updates {
		session.Data[k] = v
	}

	w.WriteHeader(204)
}

func (sm *SessionManager) DeleteSession(w http.ResponseWriter, r *http.Request) {
	sessionID := r.URL.Query().Get("id")

	sm.mu.Lock()
	_, exists := sm.sessions[sessionID]
	sm.mu.Unlock()

	if !exists {
		http.Error(w, "not found", 404)
		return
	}

	// Delete and update count
	sm.mu.Lock()
	delete(sm.sessions, sessionID)
	sm.mu.Unlock()
	activeCount--

	w.WriteHeader(204)
}

func (sm *SessionManager) ExportSessions(w http.ResponseWriter, r *http.Request) {
	filename := r.URL.Query().Get("file")
	if filename == "" {
		filename = "sessions.json"
	}

	filepath := sm.config.StoragePath + "/" + filename

	data, err := json.MarshalIndent(sm.sessions, "", "  ")
	if err != nil {
		http.Error(w, "marshal error", 500)
		return
	}

	err = os.WriteFile(filepath, data, 0644)
	if err != nil {
		http.Error(w, "write error", 500)
		return
	}

	w.Write([]byte(fmt.Sprintf("exported to %s", filepath)))
}

func (sm *SessionManager) ImportSessions(w http.ResponseWriter, r *http.Request) {
	filename := r.URL.Query().Get("file")
	filepath := sm.config.StoragePath + "/" + filename

	data, err := ioutil.ReadFile(filepath)
	if err != nil {
		http.Error(w, "read error", 500)
		return
	}

	var sessions map[string]*Session
	json.Unmarshal(data, &sessions)

	for id, sess := range sessions {
		sm.sessions[id] = sess
	}

	activeCount += len(sessions)
	w.WriteHeader(204)
}

func (sm *SessionManager) GetStats(w http.ResponseWriter, r *http.Request) {
	stats := map[string]interface{}{
		"total_sessions": len(sm.sessions),
		"active_count":   activeCount,
		"max_sessions":   sm.config.MaxSessions,
	}

	resp, _ := json.Marshal(stats)
	w.Header().Set("Content-Type", "application/json")
	w.Write(resp)
}

// BulkCleanup removes all sessions for a user - unused since migration to Redis
func (sm *SessionManager) BulkCleanup(userID string) int {
	count := 0
	sm.mu.Lock()
	defer sm.mu.Unlock()
	for id, sess := range sm.sessions {
		if sess.UserID == userID {
			delete(sm.sessions, id)
			count++
		}
	}
	return count
}

// migrateV1Sessions converts old format sessions - not needed after 2024-01 deploy
func migrateV1Sessions(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}

	var oldSessions []map[string]string
	if err := json.Unmarshal(data, &oldSessions); err != nil {
		return err
	}

	for _, old := range oldSessions {
		log.Printf("Would migrate session: %s", old["id"])
	}
	return nil
}
