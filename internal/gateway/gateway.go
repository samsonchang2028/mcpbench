// Package gateway supplies the fixed, credential-free MCP network hop.
package gateway

import (
	"bytes"
	"context"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const MaxBody = 1 << 20
const MaxHeader = 16384
const upstream = "http://mcp:8080"

// New cannot select destinations from environment, request or mounted config.
func New() http.Handler {
	return newHandler(&http.Transport{Proxy: nil, DialContext: (&net.Dialer{Timeout: time.Second}).DialContext,
		DisableKeepAlives: true, MaxConnsPerHost: 4, MaxResponseHeaderBytes: MaxHeader,
		ResponseHeaderTimeout: 6 * time.Second, DisableCompression: true})
}
func newHandler(transport http.RoundTripper) http.Handler {
	slots := make(chan struct{}, 4)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		host := r.Host == "127.0.0.1:18081" || r.Host == "localhost:18081"
		if r.URL.Path == "/healthz" {
			host = host || r.Host == "127.0.0.1:8080" || r.Host == "localhost:8080"
		}
		origins := r.Header.Values("Origin")
		if !host || len(origins) > 1 || (len(origins) == 1 && origins[0] != "" && origins[0] != "http://127.0.0.1:18081" && origins[0] != "http://localhost:18081") {
			http.Error(w, "forbidden", 403)
			return
		}
		if r.URL.RawQuery != "" || r.URL.RawPath != "" || (r.URL.Path != "/mcp" && r.URL.Path != "/healthz") {
			http.NotFound(w, r)
			return
		}
		if (r.URL.Path == "/healthz" && r.Method != "GET") || (r.URL.Path == "/mcp" && r.Method != "POST" && r.Method != "GET" && r.Method != "DELETE") {
			http.Error(w, "method", 405)
			return
		}
		n := len(r.Host)
		for k, vs := range r.Header {
			for _, v := range vs {
				n += len(k) + len(v) + 4
			}
		}
		if n > MaxHeader {
			http.Error(w, "headers", 431)
			return
		}
		select {
		case slots <- struct{}{}:
			defer func() { <-slots }()
		default:
			http.Error(w, "busy", 503)
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 6*time.Second)
		defer cancel()
		body, err := io.ReadAll(io.LimitReader(r.Body, MaxBody+1))
		r.Body.Close()
		if err != nil || len(body) > MaxBody {
			http.Error(w, "body limit", 413)
			return
		}
		target, _ := url.Parse(upstream + r.URL.Path)
		out := r.Clone(ctx)
		out.URL = target
		out.RequestURI = ""
		out.Header = r.Header.Clone()
		stripHop(out.Header)
		out.Body = io.NopCloser(bytes.NewReader(body))
		out.GetBody = nil
		out.ContentLength = int64(len(body))
		out.TransferEncoding = nil
		out.Close = true
		// RoundTrip performs no redirects; fresh connections and no GetBody prevent retries.
		response, err := transport.RoundTrip(out)
		if err != nil {
			http.Error(w, "upstream unavailable", 502)
			return
		}
		defer response.Body.Close()
		data, err := io.ReadAll(io.LimitReader(response.Body, MaxBody+1))
		if err != nil || len(data) > MaxBody {
			http.Error(w, "upstream response", 502)
			return
		}
		stripHop(response.Header)
		for k, vs := range response.Header {
			for _, v := range vs {
				w.Header().Add(k, v)
			}
		}
		w.WriteHeader(response.StatusCode)
		w.Write(data)
	})
}
func stripHop(h http.Header) {
	for _, v := range h.Values("Connection") {
		for _, k := range strings.Split(v, ",") {
			h.Del(strings.TrimSpace(k))
		}
	}
	for _, k := range []string{"Connection", "Proxy-Connection", "Keep-Alive", "Proxy-Authenticate", "Proxy-Authorization", "Te", "Trailer", "Transfer-Encoding", "Upgrade"} {
		h.Del(k)
	}
}
