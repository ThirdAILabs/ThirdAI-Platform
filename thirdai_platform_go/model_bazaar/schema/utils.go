package schema

import (
	"errors"
	"fmt"
	"log/slog"

	"gorm.io/gorm"
)

type DbError struct {
	action string
	err    error
}

func NewDbError(action string, err error) error {
	slog.Error("sql error", "action", action, "error", err)
	return DbError{action: action, err: err}
}

func (e DbError) Error() string {
	return fmt.Sprintf("sql error while %v: %v", e.action, e.err)
}

func (e DbError) Unwrap() error {
	return e.err
}

func GetUser(userId string, db *gorm.DB, loadTeams bool) (User, error) {
	var user User

	var result *gorm.DB
	if loadTeams {
		result = db.Preload("Teams").Preload("Teams.Team").First(&user, "id = ?", userId)
	} else {
		result = db.First(&user, "id = ?", userId)
	}

	if result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			return user, fmt.Errorf("no user with id %v", userId)
		}
		return user, NewDbError("retrieving user by id", result.Error)
	}

	return user, nil
}

func GetModel(modelId string, db *gorm.DB, loadDeps, loadAttrs, loadUser bool) (Model, error) {
	var model Model

	var result *gorm.DB = db
	if loadDeps {
		result = result.Preload("Dependencies")
	}
	if loadAttrs {
		result = result.Preload("Attributes")
	}
	if loadUser {
		result = result.Preload("User")
	}
	result = result.First(&model, "id = ?", modelId)

	if result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			return model, fmt.Errorf("no model with id %v", modelId)
		}
		return model, NewDbError("retrieving model by id", result.Error)
	}

	return model, nil
}

func GetUserTeam(teamId, userId string, db *gorm.DB) (*UserTeam, error) {
	var team UserTeam
	result := db.Find(&team, "team_id = ? and user_id = ?", teamId, userId)
	if result.Error != nil {
		return nil, NewDbError("retrieving user_team entry", result.Error)
	}
	if result.RowsAffected != 1 {
		return nil, nil
	}

	return &team, nil
}

func ModelExists(db *gorm.DB, modelId string) (bool, error) {
	var model Model
	result := db.Find(&model, "id = ?", modelId)
	if result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			return false, nil // Model does not exist
		}
		// adding the param in error for easy tracking
		return false, NewDbError(fmt.Sprintf("checking if model exists with modelId: %s", modelId), result.Error)

	}
	return true, nil
}

func UserExists(db *gorm.DB, userId string) (bool, error) {
	var user User
	result := db.Find(&user, "id = ?", userId)
	if result.Error != nil {
		return false, NewDbError("checking if user exists", result.Error)
	}
	return result.RowsAffected > 0, nil
}

func TeamExists(db *gorm.DB, teamId string) (bool, error) {
	var team Team
	result := db.Find(&team, "id = ?", teamId)
	if result.Error != nil {
		return false, NewDbError("checking if team exists", result.Error)
	}
	return result.RowsAffected > 0, nil
}
