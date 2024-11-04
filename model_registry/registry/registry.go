package registry

import (
	"encoding/json"
	"fmt"
	"io"
	"model_registry/schema"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/jwtauth/v5"
	"gorm.io/gorm"
)

type ModelRegistry struct {
	db *gorm.DB

	uploadAuth *jwtauth.JWTAuth

	storage Storage
}

func New(db *gorm.DB, storage Storage) *ModelRegistry {
	return &ModelRegistry{
		db:         db,
		uploadAuth: jwtauth.New("HS256", getSecret(), nil),
		storage:    storage,
	}
}

func (registry *ModelRegistry) Routes() chi.Router {
	r := chi.NewRouter()

	r.Group(func(r chi.Router) {
		r.Use(adminOnlyAuth(registry.db))

		r.Post("/new-api-key", registry.NewApiKey)
		r.Post("/delete-model", registry.DeleteModel)
		r.Post("/upload-start", registry.StartUpload)
	})

	r.Group(func(r chi.Router) {
		r.Use(jwtauth.Verifier(registry.uploadAuth))
		r.Use(jwtauth.Authenticator(registry.uploadAuth))

		r.Post("/upload-chunk", registry.UploadChunk)
		r.Post("/upload-commit", registry.CommitUpload)
	})

	r.Group(func(r chi.Router) {
		r.Use(allUsersAuth(registry.db))

		r.Post("/list-models", registry.ListModels)
		r.Post("/download-link", registry.DownloadLink)
	})

	r.Mount("/storage", registry.storage.Routes())

	return r
}

func (registry *ModelRegistry) AdminApiKey() string {
	key, err := generateApiKey(registry.db, schema.AdminRole)
	if err != nil {
		panic(err)
	}
	return key
}

type generateApiKeyRequest struct {
	Role string `json:"role"`
}

type generateApiKeyResponse struct {
	ApiKey string `json:"api_key"`
}

func (registry *ModelRegistry) NewApiKey(w http.ResponseWriter, r *http.Request) {
	var params generateApiKeyRequest
	dec := json.NewDecoder(r.Body)
	err := dec.Decode(&params)
	if err != nil {
		requestParsingError(w, err)
		return
	}

	key, err := generateApiKey(registry.db, params.Role)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	res := generateApiKeyResponse{ApiKey: key}
	writeJsonResponse(w, res)
}

func (registry *ModelRegistry) DeleteModel(w http.ResponseWriter, r *http.Request) {
	modelName := r.URL.Query().Get("model_name")
	if modelName == "" {
		http.Error(w, "Param 'name' is not present in request.", http.StatusBadRequest)
		return
	}

	model, err := registry.getModel(modelName)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to find model with name '%v': %v", modelName, err), http.StatusBadRequest)
		return
	}

	err = registry.storage.DeleteModel(model.ID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to delete model. Storage error: %v", err), http.StatusInternalServerError)
		return
	}

	result := registry.db.Unscoped().Delete(&model)
	if result.Error != nil {
		dbError(w, result.Error)
		return
	}

	w.WriteHeader(http.StatusOK)
}

type listModelsRequest struct {
	NameFilter    string `json:"name_filter"`
	TypeFilter    string `json:"type_filter"`
	SubtypeFilter string `json:"subtype_filter"`
}

func (filters *listModelsRequest) applyFilters(query *gorm.DB) *gorm.DB {
	if filters.NameFilter != "" {
		query = query.Where("name ILIKE ?", fmt.Sprintf("%%%v%%", filters.NameFilter))
	}
	if filters.TypeFilter != "" {
		query = query.Where("model_type = ?", filters.TypeFilter)
	}
	if filters.SubtypeFilter != "" {
		query = query.Where("model_subtype = ?", filters.SubtypeFilter)
	}
	return query
}

type ModelInfo struct {
	Name         string    `json:"name"`
	Id           uint      `json:"id"`
	ModelType    string    `json:"model_type"`
	ModelSubtype string    `json:"model_subtype"`
	Size         int64     `json:"size"`
	Description  string    `json:"description"`
	CreatedAt    time.Time `json:"created_at"`
}

type listModelsResponse struct {
	Models []ModelInfo `json:"models"`
}

func (registry *ModelRegistry) ListModels(w http.ResponseWriter, r *http.Request) {
	var params listModelsRequest
	dec := json.NewDecoder(r.Body)
	err := dec.Decode(&params)
	if err != nil && err != io.EOF {
		requestParsingError(w, err)
		return
	}

	var models []schema.Model
	result := params.applyFilters(registry.db.Where("access = ? and status = ?", schema.Public, schema.Commited)).Find(&models)
	if result.Error != nil {
		dbError(w, result.Error)
		return
	}

	modelInfos := make([]ModelInfo, 0, len(models))
	for _, model := range models {
		modelInfos = append(modelInfos, ModelInfo{
			Name:         model.Name,
			Id:           model.ID,
			ModelType:    model.ModelType,
			ModelSubtype: model.ModelSubtype,
			Size:         model.Size,
			Description:  model.Description,
			CreatedAt:    model.CreatedAt,
		})
	}

	res := listModelsResponse{Models: modelInfos}
	writeJsonResponse(w, res)
}

type downloadRequest struct {
	ModelName string `json:"model_name"`
}

type downloadResponse struct {
	DownloadLink string `json:"download_link"`
}

func formatDownloadName(modelName string, modelType string, compressed bool) string {
	modelFilename := strings.Replace(modelName, " ", "_", -1)
	if modelType == "ndb" {
		modelFilename += ".ndb"
	} else if modelType == "udt" {
		modelFilename += ".udt"
	} else {
		modelFilename += ".model"
	}
	if compressed {
		modelFilename += ".zip"
	}

	return modelFilename
}

func (registry *ModelRegistry) DownloadLink(w http.ResponseWriter, r *http.Request) {
	var params downloadRequest
	dec := json.NewDecoder(r.Body)
	err := dec.Decode(&params)
	if err != nil {
		requestParsingError(w, err)
		return
	}

	model, err := registry.getModel(params.ModelName)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to find model with name '%v': %v", params.ModelName, err), http.StatusBadRequest)
		return
	}

	u := r.URL.String()
	var storageUrl string
	if i := strings.Index(u, "download-link"); i >= 0 {
		storageUrl, err = url.JoinPath(u[:i], "/storage")
	} else {
		http.Error(w, "Unable to find base url.", http.StatusInternalServerError)
		return
	}

	link, err := registry.storage.GetDownloadLink(storageUrl, model.ID, formatDownloadName(model.Name, model.ModelType, model.Compressed))
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to get download link. Storage error: %v", err), http.StatusInternalServerError)
		return
	}

	res := downloadResponse{DownloadLink: link}
	writeJsonResponse(w, res)
}

type uploadRequest struct {
	ModelName    string `json:"model_name"`
	Description  string `json:"description"`
	ModelType    string `json:"model_type"`
	ModelSubtype string `json:"model_subtype"`
	Access       string `json:"access"`
	Metadata     string `json:"metadata"`
	Size         int64  `json:"size"`
	Compressed   bool   `json:"compressed"`
	Checksum     string `json:"checksum"`
}

type uploadResponse struct {
	SessionToken string `json:"session_token"`
}

func (registry *ModelRegistry) StartUpload(w http.ResponseWriter, r *http.Request) {
	var params uploadRequest
	dec := json.NewDecoder(r.Body)
	err := dec.Decode(&params)
	if err != nil {
		requestParsingError(w, err)
		return
	}

	nameRe := regexp.MustCompile(`^[\w\-]+$`)

	if !nameRe.MatchString(params.ModelName) {
		http.Error(w, "Model name must be alphanumeric with _ or -.", http.StatusBadRequest)
		return
	}

	if params.ModelType == "" || params.ModelSubtype == "" || params.Checksum == "" {
		http.Error(w, "Params 'model_name', 'model_type', 'model_subtype', and 'checksum' must be specified as non empty strings.", http.StatusBadRequest)
		return
	}

	if params.Access != schema.Public {
		http.Error(w, "Model access param must be either 'public'.", http.StatusBadRequest)
		return
	}

	if params.Size == 0 {
		http.Error(w, "Model size should be > 0.", http.StatusBadRequest)
		return
	}

	var model *schema.Model

	err = registry.db.Transaction(func(txn *gorm.DB) error {
		var count int64
		result := txn.Model(&schema.Model{}).Where("name = ?", params.ModelName).Count(&count)
		if result.Error != nil {
			return result.Error
		}
		if count != 0 {
			return fmt.Errorf("Model with name '%v' already exists", params.ModelName)
		}

		model = &schema.Model{
			Name:         params.ModelName,
			Description:  params.Description,
			ModelType:    params.ModelType,
			ModelSubtype: params.ModelSubtype,
			Access:       params.Access,
			Size:         params.Size,
			Compressed:   params.Compressed,
			Checksum:     params.Checksum,
			Status:       schema.Pending,
			StorageType:  registry.storage.Type(),
		}

		result = txn.Create(model)
		if result.Error != nil {
			return result.Error
		}

		return nil
	})

	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to create model: %v", err), http.StatusBadRequest)
		return
	}

	err = registry.storage.StartUpload(model.ID)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to start upload. Storage error: %v", err), http.StatusInternalServerError)
		return
	}

	claims := map[string]interface{}{
		"model_id": strconv.FormatUint(uint64(model.ID), 10),
		"exp":      time.Now().Add(time.Minute * 10),
	}
	_, token, err := registry.uploadAuth.Encode(claims)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error creating upload session token: %v", err), http.StatusInternalServerError)
		return
	}

	res := uploadResponse{SessionToken: token}
	writeJsonResponse(w, res)
}

type contentRange struct {
	start, end, size int64
}

func parseContentRangeHeader(value string) (contentRange, error) {
	expr := regexp.MustCompile("^bytes (\\d+)-(\\d+)/(\\d+)$")
	match := expr.FindStringSubmatch(value)
	if len(match) != 4 {
		return contentRange{}, fmt.Errorf("Invalid/missing Content-Range header")
	}

	start, err := strconv.ParseInt(match[1], 10, 64)
	if err != nil {
		return contentRange{}, err
	}
	end, err := strconv.ParseInt(match[2], 10, 64)
	if err != nil {
		return contentRange{}, err
	}
	size, err := strconv.ParseInt(match[3], 10, 64)
	if err != nil {
		return contentRange{}, err
	}

	if start > end || end > size {
		return contentRange{}, fmt.Errorf("Invalid Content-Range header parameters, start must <= end, and end must be <= size")
	}

	return contentRange{start: start, end: end, size: size}, nil
}

func getModelIdFromClaims(r *http.Request) (uint, error) {
	_, claims, err := jwtauth.FromContext(r.Context())
	if err != nil {
		return 0, fmt.Errorf("Error retrieving session token: %v", err)
	}

	modelIdStr, ok := claims["model_id"]
	if !ok {
		return 0, fmt.Errorf("Invalid session token, missing claims")
	}

	modelId, err := strconv.ParseUint(modelIdStr.(string), 10, 32)
	if err != nil {
		return 0, fmt.Errorf("Invalid session token, invalid claim format: %v", err)
	}

	return uint(modelId), nil
}

func (registry *ModelRegistry) UploadChunk(w http.ResponseWriter, r *http.Request) {
	contentRange, err := parseContentRangeHeader(r.Header.Get("Content-Range"))
	if err != nil {
		http.Error(w, fmt.Sprintf("Error parsing Content-Range header: %v", err), http.StatusBadRequest)
		return
	}

	modelId, err := getModelIdFromClaims(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	var model schema.Model
	result := registry.db.First(&model, modelId)
	if result.Error != nil {
		dbError(w, result.Error)
		return
	}

	if contentRange.size != model.Size {
		http.Error(w,
			fmt.Sprintf(
				"Model %v is specified to have size %d, but Content-Range header specifies the total size as %d",
				model.Name, int(model.Size), int(contentRange.size),
			),
			http.StatusBadRequest,
		)
		return
	}

	expectedBytes := contentRange.end - contentRange.start
	err = registry.storage.UploadChunk(modelId, contentRange.start, expectedBytes, r.Body)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to upload chunk. Storage error: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
}

func (registry *ModelRegistry) CommitUpload(w http.ResponseWriter, r *http.Request) {
	modelId, err := getModelIdFromClaims(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	var model schema.Model
	result := registry.db.First(&model, modelId)
	if result.Error != nil {
		dbError(w, result.Error)
		return
	}

	err = registry.storage.CommitUpload(modelId, model.Checksum)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error committing upload for model %v: %v", model.Name, err), http.StatusBadRequest)
		return
	}

	model.Status = schema.Commited

	result = registry.db.Save(&model)
	if result.Error != nil {
		dbError(w, result.Error)
		return
	}

	w.WriteHeader(http.StatusOK)
}

func (registry *ModelRegistry) getModel(name string) (schema.Model, error) {
	var model schema.Model
	result := registry.db.Take(&model, "name = ?", name)
	if result.Error != nil {
		return model, result.Error
	}
	if result.RowsAffected != 1 {
		return model, fmt.Errorf("Unable to find model with name '%v'", name)
	}

	return model, nil
}
