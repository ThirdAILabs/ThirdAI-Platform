package schema

import (
	"gorm.io/gorm"
)

const (
	Public = "public"
)

const (
	Pending  = "pending"
	Commited = "commited"
)

const (
	AdminRole = "admin"
	UserRole  = "user"
)

type Model struct {
	gorm.Model
	Name         string `gorm:"uniqueIndex"`
	ModelType    string
	ModelSubtype string
	Access       string // placeholder in case we want this in the future
	Size         int64
	Compressed   bool
	Description  string
	Status       string
	StorageType  string
	Checksum     string
}

type ApiKey struct {
	gorm.Model

	Key  string `gorm:"uniqueIndex"`
	Role string
}
