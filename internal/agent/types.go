package agent

import "encoding/json"

type AuthInput struct {
	SchemaVersion  int    `json:"schema_version"`
	RunID          string `json:"run_id"`
	AttemptID      string `json:"attempt_id"`
	Mode           string `json:"mode"`
	Capability     string `json:"capability"`
	IdempotencyKey string `json:"idempotency_key"`
}
type ModelConfig struct {
	Tag           string  `json:"tag"`
	Digest        string  `json:"digest"`
	ContextTokens int     `json:"context_tokens"`
	OutputTokens  int     `json:"output_tokens"`
	Temperature   float64 `json:"temperature"`
	Seed          *int    `json:"seed"`
	Think         *bool   `json:"think"`
	KeepAlive     *string `json:"keep_alive"`
}
type Budgets struct {
	ContextTokens           int `json:"context_tokens"`
	OutputTokens            int `json:"output_tokens"`
	ModelTurns              int `json:"model_turns"`
	ToolCalls               int `json:"tool_calls"`
	ToolTimeoutMS           int `json:"tool_timeout_ms"`
	DBTimeoutMS             int `json:"db_timeout_ms"`
	ModelTimeoutMS          int `json:"model_timeout_ms"`
	TaskTimeoutMS           int `json:"task_timeout_ms"`
	TransientRetries        int `json:"transient_retries"`
	PostAgentTimeoutMS      int `json:"post_agent_timeout_ms"`
	VerificationOperationMS int `json:"verification_operation_ms"`
	VerificationCalls       int `json:"verification_calls"`
	VerificationRetries     int `json:"verification_retries"`
	ArtifactBytes           int `json:"artifact_bytes"`
	DocumentBytes           int `json:"document_bytes"`
}
type AgentRequest struct {
	SchemaVersion int         `json:"schema_version"`
	RunID         string      `json:"run_id"`
	AttemptID     string      `json:"attempt_id"`
	TaskID        string      `json:"task_id"`
	Prompt        string      `json:"prompt"`
	Strategy      string      `json:"strategy"`
	CatalogID     string      `json:"catalog_id"`
	CatalogHash   string      `json:"catalog_hash"`
	PrincipalID   string      `json:"principal_id"`
	Model         ModelConfig `json:"model"`
	Budgets       Budgets     `json:"budgets"`
}
type Counts struct {
	ModelCalls int `json:"model_calls"`
	ToolCalls  int `json:"tool_calls"`
	Retries    int `json:"retries"`
}
type FinalAnswer struct {
	Text      string   `json:"text"`
	InvoiceID *string  `json:"invoice_id"`
	RecordIDs []string `json:"record_ids"`
}
type AgentResult struct {
	SchemaVersion int         `json:"schema_version"`
	RunID         string      `json:"run_id"`
	AttemptID     string      `json:"attempt_id"`
	Status        string      `json:"status"`
	FinalAnswer   FinalAnswer `json:"final_answer"`
	Counts        Counts      `json:"counts"`
}
type ToolError struct {
	Code      string `json:"code"`
	Message   string `json:"message"`
	Retryable bool   `json:"retryable"`
}
type ToolResult struct {
	ToolID  string          `json:"tool_id"`
	IsError bool            `json:"is_error"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *ToolError      `json:"error,omitempty"`
}
type Failure struct {
	Stage       string  `json:"stage"`
	Code        string  `json:"code"`
	CallID      *string `json:"call_id"`
	Reason      string  `json:"reason"`
	Attribution string  `json:"attribution"`
	Disposition string  `json:"disposition"`
}
type PostAgentBudget struct {
	AnchorID           string  `json:"anchor_id"`
	StartedAt          string  `json:"started_at"`
	DeadlineAt         string  `json:"deadline_at"`
	ElapsedMS          float64 `json:"elapsed_ms"`
	RemainingMS        float64 `json:"remaining_ms"`
	OperationTimeoutMS float64 `json:"operation_timeout_ms"`
}
type VerificationRequest struct {
	SchemaVersion       int             `json:"schema_version"`
	RunID               string          `json:"run_id"`
	AttemptID           string          `json:"attempt_id"`
	TaskID              string          `json:"task_id"`
	TaskHash            string          `json:"task_hash"`
	ConfigHash          string          `json:"config_hash"`
	InvoiceID           string          `json:"invoice_id"`
	IdempotencyKey      string          `json:"idempotency_key"`
	OriginalRequestHash string          `json:"original_request_hash"`
	OriginalArguments   json.RawMessage `json:"original_arguments"`
	ConflictArguments   json.RawMessage `json:"conflict_arguments"`
	Checks              []string        `json:"checks"`
	Budget              PostAgentBudget `json:"budget"`
}
type VerifierCheck struct {
	Check      string      `json:"check"`
	Pass       bool        `json:"pass"`
	ToolResult *ToolResult `json:"tool_result"`
	Failure    *Failure    `json:"failure"`
}
type VerifierResult struct {
	SchemaVersion       int             `json:"schema_version"`
	RunID               string          `json:"run_id"`
	AttemptID           string          `json:"attempt_id"`
	TaskID              string          `json:"task_id"`
	TaskHash            string          `json:"task_hash"`
	ConfigHash          string          `json:"config_hash"`
	Status              string          `json:"status"`
	InvoiceID           string          `json:"invoice_id"`
	IdempotencyKey      string          `json:"idempotency_key"`
	OriginalRequestHash string          `json:"original_request_hash"`
	Budget              PostAgentBudget `json:"budget"`
	Calls               int             `json:"calls"`
	Retries             int             `json:"retries"`
	Checks              []VerifierCheck `json:"checks"`
}
