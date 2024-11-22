package schema

import (
	"fmt"
	"time"
)

type Model struct {
	Id string `gorm:"primaryKey"`

	Name string
	Type string

	PublishedDate time.Time

	TrainStatus  string
	DeployStatus string

	Access            string
	DefaultPermission string

	Attributes   []ModelAttribute  `gorm:"constraint:OnDelete:CASCADE;"`
	Dependencies []ModelDependency `gorm:"foreignKey:ModelId;constraint:OnDelete:CASCADE;"`

	BaseModelId *string
	BaseModel   *Model `gorm:"constraint:OnDelete:SET NULL;"`

	UserId string
	User   *User

	TeamId *string
	Team   *Team
}

func (m *Model) GetAttributes() map[string]string {
	attrs := make(map[string]string)
	for _, attr := range m.Attributes {
		attrs[attr.Key] = attr.Value
	}
	return attrs
}

type ModelAttribute struct {
	ModelId string `gorm:"primaryKey"`
	Key     string `gorm:"primaryKey"`
	Value   string
}

type ModelDependency struct {
	ModelId      string `gorm:"primaryKey"`
	DependencyId string `gorm:"primaryKey"`

	Model      *Model `gorm:"foreignKey:ModelId"`
	Dependency *Model `gorm:"foreignKey:DependencyId"`
}

type User struct {
	Id string `gorm:"primaryKey"`

	Username string `gorm:"uniqueIndex"`
	Email    string `gorm:"uniqueIndex"`
	Password []byte `gorm:"-"`

	IsAdmin bool

	Models []Model
	Teams  []UserTeam
}

type Team struct {
	Id   string `gorm:"primaryKey"`
	Name string `gorm:"uniqueIndex"`
}

type UserTeam struct {
	UserId      string `gorm:"primaryKey;constraint:OnDelete:CASCADE;"`
	TeamId      string `gorm:"primaryKey;constraint:OnDelete:CASCADE;"`
	IsTeamAdmin bool

	User *User
	Team *Team
}

type JobLog struct {
	Id      string `gorm:"primaryKey"`
	ModelId string `gorm:"index"`
	Job     string
	Level   string
	Message string
}

func (m *Model) TrainJobName() string {
	return fmt.Sprintf("train-%v-%v", m.Type, m.Id)
}

func (m *Model) DeployJobName() string {
	return fmt.Sprintf("deploy-%v-%v", m.Type, m.Id)
}
