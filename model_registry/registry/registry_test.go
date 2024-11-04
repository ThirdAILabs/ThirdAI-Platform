package registry_test

import (
	"bytes"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"model_registry/registry"
	"model_registry/schema"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func setupRegistry(t *testing.T) *registry.ModelRegistry {
	db, err := gorm.Open(sqlite.Open("file::memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}

	err = db.AutoMigrate(&schema.Model{}, &schema.ApiKey{})
	if err != nil {
		t.Fatal(err)
	}

	localStoragePath := "./tmp/storage"

	storage := registry.NewLocalStorage(localStoragePath)

	registry := registry.New(db, storage)

	t.Cleanup(func() {
		err := os.RemoveAll(localStoragePath)
		if err != nil {
			t.Fatal(err)
		}
	})

	return registry
}

func authHeader(token string) (string, string) {
	return "Authorization", fmt.Sprintf("Bearer %v", token)
}

func TestApiKey(t *testing.T) {
	registry := setupRegistry(t)
	router := registry.Routes()

	dummyParams := map[string]interface{}{
		"model_name":    "abc",
		"model_type":    "1",
		"model_subtype": "2",
		"access":        "public",
		"size":          1,
		"checksum":      "123",
	}

	body, err := json.Marshal(dummyParams)
	if err != nil {
		t.Fatal(err)
	}

	{
		req := httptest.NewRequest("POST", "/upload-start", bytes.NewReader(body))
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Result().StatusCode != http.StatusUnauthorized {
			t.Fatal("Request should be unauthorized without token")
		}
	}

	adminKey := newApiKey(t, router, "admin", registry.AdminApiKey())
	userKey := newApiKey(t, router, "user", registry.AdminApiKey())

	{
		req := httptest.NewRequest("POST", "/upload-start", bytes.NewReader(body))
		req.Header.Add(authHeader(adminKey))
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		if w.Result().StatusCode != http.StatusOK {
			t.Fatalf("Request should succeed with admin token %d %v", w.Result().StatusCode, w.Body.String())
		}
	}

	{
		req := httptest.NewRequest("POST", "/upload-start", bytes.NewReader(body))
		req.Header.Add(authHeader(userKey))
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		if w.Result().StatusCode != http.StatusUnauthorized {
			t.Fatalf("Request should fail with user token %d %v", w.Result().StatusCode, w.Body.String())
		}
	}
}

func getChecksum(data []byte) string {
	dataChecksum, err := registry.Checksum(bytes.NewReader(data))
	if err != nil {
		panic(err)
	}
	return dataChecksum
}

func newApiKey(t *testing.T, router chi.Router, role string, adminToken string) string {
	params := map[string]interface{}{"role": role}
	body, err := json.Marshal(params)
	if err != nil {
		t.Fatal(err)
	}

	req := httptest.NewRequest("POST", "/new-api-key", bytes.NewReader(body))
	req.Header.Add("Authorization", "Bearer "+adminToken)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	resp := w.Result()
	if resp.StatusCode != http.StatusOK {
		t.Fatal("new api key failed")
	}

	result := make(map[string]string)
	json.NewDecoder(resp.Body).Decode(&result)

	return result["api_key"]
}

func uploadModel(router chi.Router, name string, data []byte, checksum string, adminKey string) error {
	params := map[string]interface{}{
		"model_name":    name,
		"description":   "a model called " + name,
		"model_type":    name,
		"model_subtype": name + "::" + name,
		"access":        "public",
		"metadata":      "",
		"size":          len(data),
		"compressed":    false,
		"checksum":      checksum,
	}

	body, err := json.Marshal(params)
	if err != nil {
		return err
	}

	req := httptest.NewRequest("POST", "/upload-start", bytes.NewReader(body))
	req.Header.Add("Authorization", "Bearer "+adminKey)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	resp := w.Result()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("upload start failed %d, %v", resp.StatusCode, w.Body.String())
	}

	result := make(map[string]string)
	json.NewDecoder(resp.Body).Decode(&result)
	session := result["session_token"]

	for start := 0; start < len(data); start += 10 {
		end := min(start+10, len(data))

		req := httptest.NewRequest("POST", "/upload-chunk", bytes.NewReader(data[start:end]))
		req.Header.Add(authHeader(session))
		req.Header.Add("Content-Range", fmt.Sprintf("bytes %d-%d/%d", start, end, len(data)))
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		if w.Result().StatusCode != http.StatusOK {
			return fmt.Errorf("upload chunk failed %d %v", w.Result().StatusCode, w.Body.String())
		}
	}

	req = httptest.NewRequest("POST", "/upload-commit", nil)
	req.Header.Add(authHeader(session))
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Result().StatusCode != http.StatusOK {
		return fmt.Errorf("upload commit failed %d, %v", w.Result().StatusCode, w.Body.String())
	}

	return nil
}

func randomBytes(n int) []byte {
	b := make([]byte, n)
	_, err := rand.Read(b)
	if err != nil {
		panic(err)
	}
	return b
}

var unauthorizedError = errors.New("download link is unauthorized")

func getDownloadLink(router chi.Router, name string, apiKey string) (string, error) {
	params := map[string]interface{}{"model_name": name}
	body, err := json.Marshal(params)
	if err != nil {
		return "", nil
	}
	req := httptest.NewRequest("POST", "/download-link", bytes.NewReader(body))
	req.Header.Add(authHeader(apiKey))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	code := w.Result().StatusCode
	if code == http.StatusUnauthorized {
		return "", unauthorizedError
	}
	if code != http.StatusOK {
		return "", fmt.Errorf("get download link failed %d %v", code, w.Body.String())
	}

	result := make(map[string]string)
	json.NewDecoder(w.Body).Decode(&result)
	return result["download_link"], nil
}

func downloadModel(router chi.Router, name string, apiKey string) ([]byte, error) {
	link, err := getDownloadLink(router, name, apiKey)
	if err != nil {
		return nil, err
	}

	req := httptest.NewRequest("GET", link, nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Result().StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download failed %d, %v", w.Result().StatusCode, w.Body.String())
	}

	return w.Body.Bytes(), nil
}

func listModels(router chi.Router, apiKey string) ([]registry.ModelInfo, error) {
	params := map[string]interface{}{}
	body, err := json.Marshal(params)
	if err != nil {
		return nil, err
	}

	req := httptest.NewRequest("POST", "/list-models", bytes.NewReader(body))
	req.Header.Add(authHeader(apiKey))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Result().StatusCode == http.StatusUnauthorized {
		return nil, unauthorizedError
	}

	if w.Result().StatusCode != http.StatusOK {
		return nil, fmt.Errorf("list models failed %d %v", w.Result().StatusCode, w.Body.String())
	}

	result := make(map[string][]registry.ModelInfo)
	json.NewDecoder(w.Body).Decode(&result)
	return result["models"], nil
}

func TestFullModelWorkflow(t *testing.T) {
	registry := setupRegistry(t)
	router := registry.Routes()

	model1 := randomBytes(107)
	model2 := randomBytes(362)

	t.Run("UploadModels", func(t *testing.T) {
		err := uploadModel(router, "abc", model1, getChecksum(model1), registry.AdminApiKey())
		if err != nil {
			t.Fatal(err)
		}
		err = uploadModel(router, "xyz", model2, getChecksum(model2), registry.AdminApiKey())
		if err != nil {
			t.Fatal(err)
		}
	})

	var adminKey, userKey string

	t.Run("CreateApiKeys", func(t *testing.T) {
		adminKey = newApiKey(t, router, "admin", registry.AdminApiKey())
		userKey = newApiKey(t, router, "user", registry.AdminApiKey())
	})

	t.Run("DownloadModelFailsNoApiKey", func(t *testing.T) {
		_, err := downloadModel(router, "xyz", "")
		if err != unauthorizedError {
			t.Fatal(err)
		}
	})

	t.Run("DownloadModelFailsInvalidApiKey", func(t *testing.T) {
		_, err := downloadModel(router, "xyz", "lasjflkjlks")
		if err != unauthorizedError {
			t.Fatal(err)
		}
	})

	t.Run("DownloadModelAdminApiKey", func(t *testing.T) {
		download, err := downloadModel(router, "xyz", adminKey)
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(model2, download) {
			t.Fatal("downloaded model doesn't match")
		}
	})

	t.Run("DownloadModelUserApiKey", func(t *testing.T) {
		download, err := downloadModel(router, "xyz", userKey)
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(model2, download) {
			t.Fatal("downloaded model doesn't match")
		}
	})

	t.Run("ListModelsFailsNoApiKey", func(t *testing.T) {
		_, err := listModels(router, "")
		if err != unauthorizedError {
			t.Fatal(err)
		}
	})

	t.Run("ListModelsFailsInvalidApiKey", func(t *testing.T) {
		_, err := listModels(router, "2asldkfj")
		if err != unauthorizedError {
			t.Fatal(err)
		}
	})

	t.Run("ListModelsAdminApiKey", func(t *testing.T) {
		models, err := listModels(router, adminKey)
		if err != nil {
			t.Fatal(err)
		}
		if len(models) != 2 {
			t.Fatal("Expected 2 models")
		}

		if models[0].Name != "abc" || models[1].Name != "xyz" {
			t.Fatal("incorrect model returned")
		}
	})

	t.Run("ListModelsUserApiKey", func(t *testing.T) {
		models, err := listModels(router, userKey)
		if err != nil {
			t.Fatal(err)
		}
		if len(models) != 2 {
			t.Fatal("Expected 2 models")
		}

		if models[0].Name != "abc" || models[1].Name != "xyz" {
			t.Fatal("incorrect model returned")
		}
	})

	t.Run("DeleteModel", func(t *testing.T) {
		req := httptest.NewRequest("POST", "/delete-model?model_name=xyz", nil)
		req.Header.Add(authHeader(adminKey))
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		if w.Result().StatusCode != http.StatusOK {
			t.Fatalf("failed to delete model %d %v", w.Result().StatusCode, w.Body.String())
		}

		models, err := listModels(router, userKey)
		if err != nil {
			t.Fatal(err)
		}
		if len(models) != 1 {
			t.Fatalf("Expected only 1 result after deleting model")
		}
	})
}

func TestModelChecksums(t *testing.T) {
	registry := setupRegistry(t)
	router := registry.Routes()

	token := registry.AdminApiKey()

	model := randomBytes(528)
	checksum := getChecksum(model)
	model[48] = model[48] + 1 // Corrupt byte

	err := uploadModel(router, "abc", model, checksum, token)
	if err == nil {
		t.Fatal("Checksum mismatch should cause upload to fail")
	}

	if !strings.Contains(err.Error(), "Checksum doesn't match for model") {
		t.Fatal("Expected checksum error")
	}
}
