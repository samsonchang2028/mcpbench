package ollama

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
)

type roundtrip func(*http.Request) (*http.Response, error)

func (f roundtrip) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }
func TestNativeRequestAndBoundedResponses(t *testing.T) {
	for _, body := range []string{`{"message":{"role":"assistant","content":"ok"},"done":true,"prompt_eval_count":1,"eval_count":1}`, `{"message":{"role":"assistant","content":"ok"},"done":true,"done":false}`, strings.Repeat("x", 1048577), `{"message":{"role":"assistant"},"done":true,"eval_count":-1}`} {
		t.Run(body[:min(len(body), 45)], func(t *testing.T) {
			c := New()
			c.HTTP.Transport = roundtrip(func(r *http.Request) (*http.Response, error) {
				if r.URL.String() != Endpoint || r.Method != "POST" {
					t.Fatal("untrusted target")
				}
				var q map[string]any
				json.NewDecoder(r.Body).Decode(&q)
				if q["stream"] != false || q["model"] != "scripted" {
					t.Fatal(q)
				}
				return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body))}, nil
			})
			out, e := c.Chat(context.Background(), Request{Model: "scripted", Stream: false})
			if strings.Contains(body, `"prompt_eval_count":1`) {
				if e != nil || out.Message.Content != "ok" {
					t.Fatal(e)
				}
			} else if e == nil {
				t.Fatal("accepted invalid response")
			}
		})
	}
}
func TestNoProxyOrRedirect(t *testing.T) {
	c := New()
	if c.HTTP.Transport.(*http.Transport).Proxy != nil || c.HTTP.CheckRedirect(nil, nil) == nil {
		t.Fatal("proxy/redirect enabled")
	}
}
func TestStrictWire(t *testing.T) {
	for _, s := range []string{`{"x":1.0}`, `{"x":"\udc00"}`, `{"x":1,"x":2}`, `{"x":1e3}`} {
		if _, e := StrictJSON([]byte(s)); e == nil {
			t.Fatal("accepted", s)
		}
	}
	if _, e := StrictJSON([]byte(`{"duration_ms":1.25,"x":"\ud83d\ude00"}`)); e != nil {
		t.Fatal(e)
	}
}

func TestInvalidArgumentsRemainRawForAgentAccounting(t *testing.T) {
	body := `{"message":{"role":"assistant","tool_calls":[{"function":{"name":"billing_create_draft_invoice","arguments":{"quantity":2.0}}}]},"done":true}`
	c := New()
	c.HTTP.Transport = roundtrip(func(*http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body))}, nil
	})
	r, e := c.Chat(context.Background(), Request{Model: "scripted"})
	if e != nil || len(r.Message.ToolCalls) != 1 || string(r.Message.ToolCalls[0].Function.Arguments) != `{"quantity":2.0}` {
		t.Fatalf("lost invalid selection: %+v %v", r, e)
	}
}

func TestDuplicateArgumentBytesSurviveForStrictRejection(t *testing.T) {
	body := `{"message":{"role":"assistant","tool_calls":[{"function":{"name":"billing_list_items","arguments":{"x":1,"x":2}}}]},"done":true}`
	c := New()
	c.HTTP.Transport = roundtrip(func(*http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body))}, nil
	})
	r, e := c.Chat(context.Background(), Request{Model: "scripted"})
	if e != nil || len(r.Message.ToolCalls) != 1 || string(r.Message.ToolCalls[0].Function.Arguments) != `{"x":1,"x":2}` {
		t.Fatalf("lost rejected attempt: %+v %v", r, e)
	}
	if _, e = StrictJSON(r.Message.ToolCalls[0].Function.Arguments); e == nil {
		t.Fatal("strict tool boundary accepted duplicate")
	}
}
