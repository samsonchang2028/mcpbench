// Command agent is a fail-closed scaffold; it performs no runtime work.
package main

import (
	"fmt"
	"os"
)

func main() {
	fmt.Fprintln(os.Stderr, "mcpbench: agent unavailable until its runtime DAG gates pass")
	os.Exit(2)
}
