// Command scripted-agent is a deterministic integration-only substitute for the
// model. It uses the real agent loop, SDK transport and server. It never calls
// Ollama; its image identity must be recorded as scripted rather than Qwen proof.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"mcpbench/internal/agent"
	"mcpbench/internal/ollama"
	"mcpbench/observability"
)

var scenario = "smoke"

type scriptedModel struct{ turn int }

func (m *scriptedModel) Chat(ctx context.Context, q ollama.Request) (ollama.Response, error) {
	if ctx.Err() != nil {
		return ollama.Response{}, ctx.Err()
	}
	m.turn++
	name, args := "", "{}"
	switch m.turn {
	case 1:
		name = "billing_list_customers"
	case 2:
		name = "billing_list_items"
	case 3:
		name = agent.CreateTool
		quantity := 2
		if scenario == "wrong-write" {
			quantity = 3
		}
		args = fmt.Sprintf(`{"customer_id":"CUST-001","invoice_date":"2026-11-07","due_date":"2026-11-21","lines":[{"item_id":"SVC-CONSULT","quantity":%d}]}`, quantity)
	default:
		for i := len(q.Messages) - 1; i >= 0; i-- {
			message := q.Messages[i]
			if message.Role == "tool" && message.ToolName == agent.CreateTool {
				var out struct {
					Invoice struct {
						ID string `json:"invoice_id"`
					} `json:"invoice"`
				}
				if json.Unmarshal([]byte(message.Content), &out) != nil || out.Invoice.ID == "" {
					return ollama.Response{}, errors.New("scripted result")
				}
				return ollama.Response{Done: true, Message: ollama.Message{Role: "assistant", Content: "Created draft " + out.Invoice.ID + "."}}, nil
			}
		}
		return ollama.Response{}, errors.New("scripted history")
	}
	return ollama.Response{Done: true, Message: ollama.Message{Role: "assistant", ToolCalls: []ollama.ToolCall{{ID: fmt.Sprintf("scripted-%d", m.turn), Function: ollama.Function{Name: name, Arguments: json.RawMessage(args)}}}}}, nil
}

// lostReply exercises a real committed server reply discarded at the client
// boundary. The loop retries unchanged arguments/key once; no fake invoice is
// supplied. It is a response-loss fault, never a claimed real network outage.
type lostReply struct {
	agent.Tools
	lost bool
}

func (t *lostReply) Call(ctx context.Context, name string, args json.RawMessage) (agent.ToolResult, error) {
	result, err := t.Tools.Call(ctx, name, args)
	if err == nil && !result.IsError && name == agent.CreateTool && !t.lost {
		t.lost = true
		return agent.ToolResult{}, agent.TransientError{}
	}
	return result, err
}
func main() {
	if err := execute(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "mcpbench: scripted integration child failed")
		os.Exit(1)
	}
}

type toolConnection interface {
	agent.Tools
	Close() error
}

func execute(args []string) error {
	return executeWithConnector(args, func(ctx context.Context, auth agent.AuthInput) (toolConnection, error) {
		return agent.ConnectMCP(ctx, auth)
	})
}

func executeWithConnector(args []string, connect func(context.Context, agent.AuthInput) (toolConnection, error)) error {
	entered := time.Now()
	if len(args) != 7 || (args[0] != "run" && args[0] != "verify") || args[1] != "--request" || args[3] != "--auth" || args[5] != "--output" {
		return errors.New("fixed arguments")
	}
	raw, err := agent.ReadDocument(args[2])
	if err != nil {
		return err
	}
	secret, err := agent.ReadDocument(args[4])
	if err != nil {
		return err
	}
	var auth agent.AuthInput
	if agent.Decode("AuthInput", secret, &auth) != nil || agent.CheckOutput(args[6]) != nil {
		return errors.New("private input")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 300*time.Second)
	defer cancel()
	writer, err := observability.New(filepath.Join(args[6], "events.jsonl"), observability.Context{RunID: auth.RunID, AttemptID: auth.AttemptID, Source: "agent"}, observability.Options{Validate: agent.ValidateEvent, Secrets: []string{auth.Capability, auth.IdempotencyKey}})
	if err != nil {
		return err
	}
	defer writer.Close()
	connection, err := connect(ctx, auth)
	if err != nil {
		return err
	}
	defer connection.Close()
	var value any
	status := "failed"
	if args[0] == "run" {
		var request agent.AgentRequest
		if agent.Decode("AgentRequest", raw, &request) != nil || auth.Mode != "agent" {
			return errors.New("request")
		}
		var tools agent.Tools = connection
		if scenario == "lost-reply" {
			tools = &lostReply{Tools: connection}
		}
		result, e := (agent.Runner{Model: &scriptedModel{}, Tools: tools, Events: writer}).Run(ctx, request, auth)
		if e != nil {
			return errors.New("scripted loop")
		}
		value = result
		status = result.Status
	} else {
		var request agent.VerificationRequest
		if agent.Decode("VerificationRequest", raw, &request) != nil {
			return errors.New("verification request")
		}
		result, e := agent.VerifySince(ctx, request, auth, connection, writer, entered)
		if e != nil {
			return errors.New("verification")
		}
		value = result
		status = result.Status
	}
	if err := writer.Close(); err != nil {
		return err
	}
	if err := agent.WriteResult(args[6], value); err != nil {
		return err
	}
	if status != "completed" {
		return errors.New("scripted execution failed")
	}
	return nil
}
