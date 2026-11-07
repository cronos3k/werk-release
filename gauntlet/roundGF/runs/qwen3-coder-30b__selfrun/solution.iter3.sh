#!/bin/bash

# Since we're in a Windows environment with Git Bash, let's try to detect if we can use MSVC
# The task says we should probe for what exists rather than assuming

echo "=== PREDICTION ==="
echo "Files used: tools/llama2c/run.c, tools/llama2c/win.c, tools/llama2c/win.h, model/stories15M.bin, model/tokenizer.bin"
echo "Unblocking file: tools/llama2c/BUILD-AND-RUN.md (contains build instructions)"
echo "Build command: cl /nologo /O2 /Fe:run.exe tools\\llama2c\\run.c tools\\llama2c\\win.c"
echo "Runner invocation: ./run.exe model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i \"Once upon a time\""
echo "Expected output text from testvectors/generate-once-upon-a-time.stdout.txt:"
echo "Once upon a time, there was a little girl named Lily. She loved to play outside in the sunshine. One day, she saw a big, red ball in the sky. It was the sun! She thought it was so pretty."
echo "Lily wanted to play with the ball, but it was"
echo ""
echo "Expected SHA256 (LF): 32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5"
echo "=== END PREDICTION ==="

# Check what compilers are available
echo "Checking for available compilers..."
if command -v cl &> /dev/null; then
    echo "Found MSVC compiler (cl)"
    COMPILER="MSVC"
elif command -v gcc &> /dev/null; then
    echo "Found GCC compiler"
    COMPILER="GCC"
else
    echo "No suitable compiler found"
    exit 1
fi

# Try to build with MSVC first since that's what was verified
if [ "$COMPILER" = "MSVC" ]; then
    echo "Building with MSVC: cl /nologo /O2 /Fe:run.exe tools\\llama2c\\run.c tools\\llama2c\\win.c"
    cl /nologo /O2 /Fe:run.exe tools\llama2c\run.c tools\llama2c\win.c
    if [ $? -eq 0 ]; then
        echo "MSVC build successful"
        RUNNER="./run.exe"
    else
        echo "MSVC build failed"
        # Try to see what error we get
        cl /nologo /O2 /Fe:run.exe tools\llama2c\run.c tools\llama2c\win.c 2>&1 | head -10
        exit 1
    fi
elif [ "$COMPILER" = "GCC" ]; then
    echo "Note: GCC build will likely fail as documented in BUILD-AND-RUN.md"
    echo "Attempting build with GCC anyway..."
    # Try to build with GCC but we know it will have issues according to docs
    gcc -O3 -o run.exe tools/llama2c/run.c tools/llama2c/win.c -lm 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "GCC build successful"
        RUNNER="./run.exe"
    else
        echo "GCC build failed as expected per documentation"
        echo "This is expected behavior according to BUILD-AND-RUN.md section 2c"
        echo "The script will now exit since we cannot build a working binary"
        exit 1
    fi
fi

echo ""
echo "=== BUILD COMMAND ==="
if [ "$COMPILER" = "MSVC" ]; then
    echo "cl /nologo /O2 /Fe:run.exe tools\\llama2c\\run.c tools\\llama2c\\win.c"
else
    echo "gcc -O3 -o run.exe tools/llama2c/run.c tools/llama2c/win.c -lm"
fi
echo "=== END BUILD COMMAND ==="

echo ""
echo "=== RUNNER INVOCATION ==="
echo "$RUNNER model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i \"Once upon a time\""
echo "=== END RUNNER INVOCATION ==="

# If we got here, we should be able to run
if [ -n "$RUNNER" ]; then
    echo ""
    echo "=== RUNNING MODEL ==="
    OUTPUT=$($RUNNER model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i "Once upon a time" 2>/dev/null)
    TIMING=$($RUNNER model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i "Once upon a time" 2>&1 >/dev/null | grep "achieved tok/s")

    echo "$OUTPUT"
    echo ""
    echo "Timing info: $TIMING"
    echo "=== END RUNNING MODEL ==="

    # Calculate SHA256 of output (LF normalized)
    echo ""
    echo "=== OUTPUT VERIFICATION ==="
    OUTPUT_LF=$(echo "$OUTPUT" | tr -d '\r')
    SHA256_OUTPUT=$(echo -n "$OUTPUT_LF" | sha256sum | cut -d' ' -f1)

    echo "Actual SHA256 (LF): $SHA256_OUTPUT"
    echo "Expected SHA256 (LF): 32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5"

    if [ "$SHA256_OUTPUT" = "32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5" ]; then
        echo "✓ SHA256 MATCHES"
    else
        echo "✗ SHA256 DOES NOT MATCH"
    fi

    # Compare with expected text
    echo ""
    echo "=== TEXT VERIFICATION ==="
    EXPECTED_TEXT=$(cat testvectors/generate-once-upon-a-time.stdout.txt)
    echo "Expected text:"
    echo "$EXPECTED_TEXT"
    echo ""
    echo "Actual text:"
    echo "$OUTPUT"

    if [ "$OUTPUT_LF" = "$EXPECTED_TEXT" ]; then
        echo "✓ TEXT MATCHES EXACTLY"
    else
        echo "✗ TEXT DOES NOT MATCH EXACTLY"
        # Check if it's just a line ending issue
        if [ "$(echo -n "$OUTPUT_LF" | wc -l)" = "$(echo -n "$EXPECTED_TEXT" | wc -l)" ]; then
            echo "  (Same number of lines, but content differs)"
        fi
    fi

    # Verify against test vectors
    echo ""
    echo "=== TEST VECTOR VERIFICATION ==="
    echo "Vector ID: once-upon-a-time"
    echo "Prompt: Once upon a time"
    echo "Steps: 64"
    echo "Temperature: 0.0"
    echo "Expected stdout_bytes_lf: 234"
    ACTUAL_BYTES=$(echo -n "$OUTPUT_LF" | wc -c)
    echo "Actual stdout_bytes_lf: $ACTUAL_BYTES"

    if [ "$ACTUAL_BYTES" = "234" ]; then
        echo "✓ BYTE COUNT MATCHES"
    else
        echo "✗ BYTE COUNT DOES NOT MATCH"
    fi

    echo ""
    echo "=== VERIFICATION SUMMARY ==="
    if [ "$SHA256_OUTPUT" = "32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5" ] && [ "$ACTUAL_BYTES" = "234" ]; then
        echo "✓ ALL VERIFICATIONS PASSED - MODEL IS WORKING CORRECTLY"
    else
        echo "✗ SOME VERIFICATIONS FAILED"
    fi
else
    echo "Could not build a working runner"
    exit 1
fi

echo ""
echo "=== FILES USED ==="
echo "tools/llama2c/run.c"
echo "tools/llama2c/win.c" 
echo "tools/llama2c/win.h"
echo "model/stories15M.bin"
echo "model/tokenizer.bin"
echo "testvectors/generate-once-upon-a-time.stdout.txt"
echo "tools/llama2c/BUILD-AND-RUN.md"
echo ""
echo "Unblocking file: tools/llama2c/BUILD-AND-RUN.md (contained build instructions)"
echo "Compiler used: $COMPILER"

# Since we know MSVC is the only working approach, let's try to be more specific
if command -v cl &> /dev/null; then
    echo "Running on Windows with MSVC available - build should have succeeded"
else
    echo "Warning: This script may not work correctly without proper Windows MSVC environment"
fi
