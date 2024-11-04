package schema

import (
	"errors"
	"fmt"

	"gorm.io/gorm"
)

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
		return user, fmt.Errorf("error locating user with id %v: %v", userId, result.Error)
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
		return model, fmt.Errorf("error locating model with id %v: %v", modelId, result.Error)
	}

	return model, nil
}

func GetUserTeam(teamId, userId string, db *gorm.DB) (*UserTeam, error) {
	var team UserTeam
	result := db.Find(&team, "team_id = ? and user_id = ?", teamId, userId)
	if result.Error != nil {
		return nil, fmt.Errorf("database error: %v", result.Error)
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
		return false, fmt.Errorf("database error: %v", result.Error)
	}
	return result.RowsAffected > 0, nil
}

func UserExists(db *gorm.DB, userId string) (bool, error) {
	var user User
	result := db.Find(&user, "id = ?", userId)
	if result.Error != nil {
		return false, fmt.Errorf("database error: %v", result.Error)
	}
	return result.RowsAffected > 0, nil
}

func TeamExists(db *gorm.DB, teamId string) (bool, error) {
	var team Team
	result := db.Find(&team, "id = ?", teamId)
	if result.Error != nil {
		return false, fmt.Errorf("database error: %v", result.Error)
	}
	return result.RowsAffected > 0, nil
}
