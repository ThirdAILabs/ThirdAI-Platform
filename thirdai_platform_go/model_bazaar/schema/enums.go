package schema

import "fmt"

const (
	NotStarted = "not_started"
	Starting   = "starting"
	InProgress = "in_progress"
	Stopped    = "stopped"
	Complete   = "complete"
	Failed     = "failed"
)

const (
	Private   = "private"
	Protected = "protected"
	Public    = "public"
)

func CheckValidStatus(status string) error {
	switch status {
	case NotStarted, Starting, InProgress, Stopped, Complete, Failed:
		return nil
	default:
		return fmt.Errorf("invalid status '%v'", status)
	}
}

func CheckValidAccess(access string) error {
	switch access {
	case Public, Private, Protected:
		return nil
	default:
		return fmt.Errorf("invalid access %v, must be 'public', 'private', or 'protected'", access)
	}
}

const (
	ReadPerm  = "read"
	WritePerm = "write"
)

func CheckValidPermission(permission string) error {
	if permission == ReadPerm || permission == WritePerm {
		return nil
	}
	return fmt.Errorf("invalid permission %v, must be 'read' or 'write'", permission)
}

const (
	NdbModel      = "ndb"
	NlpTokenModel = "nlp-token"
	NlpTextModel  = "nlp-text"
)

func CheckValidModelType(modelType string) error {
	switch modelType {
	case NdbModel, NlpTokenModel, NlpTextModel:
		return nil
	default:
		return fmt.Errorf("invalid model type '%v'", modelType)
	}
}
