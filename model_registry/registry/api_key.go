package registry

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"model_registry/schema"
	"net/http"
	"strings"

	"gorm.io/gorm"
)

func generateApiKey(db *gorm.DB, role string) (string, error) {
	if role != schema.AdminRole && role != schema.UserRole {
		return "", fmt.Errorf("Invalid role for key, must be 'admin' or 'user'.")
	}
	b := make([]byte, 64)

	_, err := rand.Read(b)
	if err != nil {
		return "", err
	}

	apiKey := base64.StdEncoding.EncodeToString(b)

	entry := schema.ApiKey{Key: apiKey, Role: role}

	result := db.Create(&entry)
	if result.Error != nil {
		return "", fmt.Errorf("Database error creating api key: %v", result.Error)
	}

	return apiKey, nil
}

type roleAuthMiddleware struct {
	db        *gorm.DB
	next      http.Handler
	adminOnly bool
}

func (auth *roleAuthMiddleware) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	key := tokenFromHeader(r)
	if key == "" {
		http.Error(w, "Api key is missing in request", http.StatusUnauthorized)
		return
	}

	var keyEntry schema.ApiKey
	result := auth.db.Find(&keyEntry, "key = ?", key)
	if result.Error != nil {
		http.Error(w, fmt.Sprintf("db error retrieving api key: %v", result.Error), http.StatusInternalServerError)
		return
	}

	if result.RowsAffected != 1 {
		http.Error(w, "invalid api key", http.StatusUnauthorized)
		return
	}

	if auth.adminOnly && keyEntry.Role != schema.AdminRole {
		http.Error(w, "api must have admin permissions to access endpoint", http.StatusUnauthorized)
		return
	}

	ctx := r.Context()
	ctx = context.WithValue(ctx, "api-key", key)

	auth.next.ServeHTTP(w, r.WithContext(ctx))
}

func adminOnlyAuth(db *gorm.DB) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return &roleAuthMiddleware{
			db: db, next: next, adminOnly: true,
		}
	}
}

func allUsersAuth(db *gorm.DB) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return &roleAuthMiddleware{
			db: db, next: next, adminOnly: false,
		}
	}
}

func tokenFromHeader(r *http.Request) string {
	// Get token from authorization header.
	bearer := r.Header.Get("Authorization")
	if len(bearer) > 7 && strings.ToUpper(bearer[0:6]) == "BEARER" {
		return bearer[7:]
	}
	return ""
}
