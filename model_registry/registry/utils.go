package registry

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"gorm.io/gorm"
)

func getSecret() []byte {
	// This is only used for jwt secrets, if the server restarts the only issue is any
	// tokens issued before the restart (that aren't yet expired) will be invalidated.
	b := make([]byte, 16)

	_, err := rand.Read(b)
	if err != nil {
		panic(err)
	}

	return b
}

func requestParsingError(w http.ResponseWriter, err error) {
	http.Error(w, fmt.Sprintf("Error parsing request body: %v", err), http.StatusBadRequest)
}

func dbError(w http.ResponseWriter, err error) {
	if err == gorm.ErrRecordNotFound {
		http.Error(w, fmt.Sprintf("Unable to retrieve record for request: %v", err), http.StatusBadRequest)
	} else {
		http.Error(w, fmt.Sprintf("Database error: %v", err), http.StatusInternalServerError)
	}
}

func Checksum(data io.Reader) (string, error) {
	h := sha256.New()
	if _, err := io.Copy(h, data); err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(h.Sum(nil)), nil
}

func writeJsonResponse(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	err := json.NewEncoder(w).Encode(data)
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to write response: %v", err), http.StatusBadRequest)
	}
}
