// ailineage: urn:sha256:32d76db5a97e2c12d7ffb521cf6ec6c5337fa9e26685fb03cc067e169dbb9de3
package main

import (
	"fmt"
	"os"
)

func main() {
	name := "world"
	if len(os.Args) > 1 {
		name = os.Args[1]
	}
	fmt.Printf("hello, %s\n", name)
}
