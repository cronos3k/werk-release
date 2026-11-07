#!/bin/bash

# Prediction: Based on the package contents, I need to:
# 1. Build the C runtime from tools/llama2c/run.c and tools/llama2c/win.c (since we're on Windows)
# 2. Run it with the specified command line to generate text
# 3. Compare output against test vectors

echo "=== PREDICTION ==="
echo "Based on BUILD-AND-RUN.md, I will:"
echo "1. Build using MSVC: cl /nologo /O2 /Fe:run.exe tools\\llama2c\\run.c tools\\llama2c\\win.c"
echo "2. Run with: ./run model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i \"Once upon a time\""
echo "3. Expected output should match the test vector for 'once-upon-a-time' with sha256: 32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5"
echo "4. The build should use MSVC since that's what was verified in the package"

# Check if cl (MSVC) is available
if command -v cl &> /dev/null; then
    echo "Using MSVC compiler (cl)"
    BUILD_CMD="cl /nologo /O2 /Fe:run.exe tools\\llama2c\\run.c tools\\llama2c\\win.c"
    RUN_CMD="./run.exe model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i \"Once upon a time\""
    COMPILER="MSVC"
elif command -v gcc &> /dev/null; then
    echo "Using GCC compiler (gcc)"
    BUILD_CMD="gcc -O3 -o run tools/llama2c/run.c -lm"
    RUN_CMD="./run model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i \"Once upon a time\""
    COMPILER="GCC"
else
    echo "No suitable compiler found"
    exit 1
fi

echo ""
echo "=== BUILDING ==="
echo "Build command: $BUILD_CMD"

# Build the runtime
eval "$BUILD_CMD" 2>&1
BUILD_EXIT=$?
if [ $BUILD_EXIT -ne 0 ]; then
    echo "Build failed with exit code $BUILD_EXIT"
    exit 1
fi

echo ""
echo "=== RUNNING ==="
echo "Run command: $RUN_CMD"

# Run the model
OUTPUT_FILE=$(mktemp)
ERROR_FILE=$(mktemp)

# Capture both stdout and stderr
eval "$RUN_CMD" > "$OUTPUT_FILE" 2> "$ERROR_FILE"
RUN_EXIT=$?

echo "Exit code: $RUN_EXIT"

# Show timing info from stderr
echo ""
echo "=== TIMING INFO ==="
cat "$ERROR_FILE"

# Read the output
echo ""
echo "=== OUTPUT ==="
cat "$OUTPUT_FILE"

# Calculate SHA256 of output (LF normalized)
NORMALIZED_OUTPUT=$(tr -d '\r' < "$OUTPUT_FILE")
SHA256=$(echo -n "$NORMALIZED_OUTPUT" | sha256sum | cut -d' ' -f1)

echo ""
echo "=== VERIFICATION ==="
echo "Computed SHA256: $SHA256"
echo "Expected SHA256: 32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5"

if [ "$SHA256" = "32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5" ]; then
    echo "✓ OUTPUT MATCHES TEST VECTOR"
else
    echo "✗ OUTPUT DOES NOT MATCH TEST VECTOR"
fi

# Also check the content matches expected text
EXPECTED_TEXT="Once upon a time, there was a little girl named Lily. She loved to play outside in the sunshine. One day, she saw a big, red ball in the sky. It was the sun! She thought it was so pretty.
Lily wanted to play with the ball, but it was"

ACTUAL_TEXT=$(tr -d '\r' < "$OUTPUT_FILE")
if [[ "$ACTUAL_TEXT" == *"$EXPECTED_TEXT"* ]]; then
    echo "✓ OUTPUT CONTENT MATCHES EXPECTED TEXT"
else
    echo "✗ OUTPUT CONTENT DOES NOT MATCH EXPECTED TEXT"
fi

# Cleanup
rm -f "$OUTPUT_FILE" "$ERROR_FILE"

echo ""
echo "=== SUMMARY ==="
echo "Files used: tools/llama2c/run.c, tools/llama2c/win.c, model/stories15M.bin, model/tokenizer.bin"
echo "Build command: $BUILD_CMD"
echo "Run command: $RUN_CMD"
echo "Compiler used: $COMPILER"
echo "Verification: $(if [ "$SHA256" = "32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5" ]; then echo "PASS"; else echo "FAIL"; fi)"
