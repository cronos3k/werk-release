#!/bin/bash
set -u

# Working directory is where selfrun-v1.werk is.
ROOT="$(pwd)"
WORK="$ROOT/_work"
rm -rf "$WORK"
mkdir -p "$WORK"

# Extract the zip using python (store-mode, no compression).
python - <<'PY'
import zipfile, sys
z = zipfile.ZipFile('selfrun-v1.werk')
z.extractall('_work')
print("Extracted", len(z.namelist()), "entries")
PY

cd "$WORK"

# Read test vectors and expected outputs.
python - <<'PY'
import json
with open('testvectors/vectors.json') as f:
    data = json.load(f)
for v in data['vectors']:
    print("VECTOR", v['vector_id'])
    print("PROMPT:", v['prompt'])
    print("STEPS:", v['steps'])
    print("EXPECTED_STDOUT:")
    print(v['stdout_text'])
    print("EXPECTED_SHA256_LF:", v['stdout_sha256_lf'])
    print("---")
PY

# Print prediction and source.
echo "PREDICTION: The program will output exactly the stdout_text from testvectors/vectors.json for each vector, because we will build and run with the exact commands and temperature 0.0 (greedy argmax)."
echo "PREDICTION SOURCE: testvectors/vectors.json (stdout_text fields)."

# Probe compilers.
COMPILER=""
BUILD_CMD=""
if command -v cl >/dev/null 2>&1; then
    COMPILER="cl"
    echo "Compiler found: MSVC cl"
elif command -v gcc >/dev/null 2>&1; then
    COMPILER="gcc"
    echo "Compiler found: gcc (mingw)"
else
    echo "No supported compiler found (cl or gcc). Exiting."
    exit 1
fi

# Build.
if [ "$COMPILER" = "cl" ]; then
    BUILD_CMD="cl /nologo /O2 /Fe:run.exe tools/llama2c/run.c tools/llama2c/win.c"
    echo "Build command: $BUILD_CMD"
    eval "$BUILD_CMD" > build_out.txt 2> build_err.txt
    BUILD_STATUS=$?
else
    # Patch win.c for mingw: cast and guard.
    cp tools/llama2c/win.c win_patched.c
    # Fix 1: cast oldProtect to PDWORD.
    sed -i 's/VirtualProtect(addr, len, newProtect, &oldProtect)/VirtualProtect(addr, len, newProtect, (PDWORD)\&oldProtect)/' win_patched.c
    # Fix 2: guard clock_gettime definition.
    # Insert #if !defined(__MINGW32__) before the function and #endif after.
    python - <<'PY'
with open('win_patched.c', 'r') as f:
    lines = f.readlines()
out = []
in_clock = False
for line in lines:
    if line.strip().startswith('int clock_gettime('):
        out.append('#if !defined(__MINGW32__)\n')
        in_clock = True
    out.append(line)
    if in_clock and line.strip() == '}':
        out.append('#endif\n')
        in_clock = False
with open('win_patched.c', 'w') as f:
    f.writelines(out)
PY
    BUILD_CMD="gcc -O3 -o run.exe tools/llama2c/run.c win_patched.c -lm"
    echo "Build command: $BUILD_CMD"
    eval "$BUILD_CMD" > build_out.txt 2> build_err.txt
    BUILD_STATUS=$?
fi

echo "Build exit code: $BUILD_STATUS"
if [ $BUILD_STATUS -ne 0 ]; then
    echo "Build failed. stderr:"
    cat build_err.txt
    exit 1
fi
echo "Build output (stdout):"
cat build_out.txt
echo "Build output (stderr):"
cat build_err.txt

# Run the two vectors.
declare -a ARGV1=("./run.exe" "model/stories15M.bin" "-z" "model/tokenizer.bin" "-t" "0.0" "-n" "64" "-i" "Once upon a time")
declare -a ARGV2=("./run.exe" "model/stories15M.bin" "-z" "model/tokenizer.bin" "-t" "0.0" "-n" "32" "-i" "The little robot")

run_vector() {
    local name="$1"
    shift
    local outfile="out_${name}.txt"
    local errfile="err_${name}.txt"
    echo "Running vector $name with command: $*"
    "$@" > "$outfile" 2> "$errfile"
    local status=$?
    echo "Runner exit code: $status"
    echo "Runner stderr:"
    cat "$errfile"
    # Normalize CRLF to LF.
    python - <<PY
import sys
with open('$outfile', 'rb') as f:
    data = f.read().replace(b'\r\n', b'\n')
with open('${outfile}.lf', 'wb') as f:
    f.write(data)
PY
    echo "Normalized stdout (LF):"
    cat "${outfile}.lf"
    echo "---"
}

run_vector "once" "${ARGV1[@]}"
run_vector "robot" "${ARGV2[@]}"

# Verify against vectors.json.
python - <<'PY'
import json, hashlib, sys

with open('testvectors/vectors.json') as f:
    data = json.load(f)

for v in data['vectors']:
    vid = v['vector_id']
    outfile = f'out_{vid}.txt.lf'
    with open(outfile, 'rb') as f:
        actual = f.read()
    actual_sha = hashlib.sha256(actual).hexdigest()
    expected_sha = v['stdout_sha256_lf']
    expected_text = v['stdout_text'].encode('utf-8')
    match = (actual == expected_text) and (actual_sha == expected_sha)
    print(f"Vector {vid}:")
    print(f"  Actual sha256 (LF): {actual_sha}")
    print(f"  Expected sha256 (LF): {expected_sha}")
    print(f"  Byte match: {actual == expected_text}")
    print(f"  Hash match: {actual_sha == expected_sha}")
    print(f"  VERDICT: {'PASS' if match else 'FAIL'}")
    if not match:
        print("  Actual stdout:")
        print(actual.decode('utf-8', errors='replace'))
        print("  Expected stdout:")
        print(expected_text.decode('utf-8', errors='replace'))
    print("---")
PY

# Compute digests of files we used.
echo "Digests of files used:"
for f in tools/llama2c/run.c tools/llama2c/win.c tools/llama2c/win.h tools/llama2c/BUILD-AND-RUN.md spec/layouts/llama2c-checkpoint.layout.txt spec/layouts/llama2c-tokenizer.layout.txt testvectors/vectors.json model/stories15M.bin model/tokenizer.bin; do
    if [ -f "$f" ]; then
        sha=$(python -c "import hashlib; print(hashlib.sha256(open('$f','rb').read()).hexdigest())")
        echo "  $f: $sha"
    fi
done

echo "Files used: the whole package, but key ones: tools/llama2c/run.c, win.c, win.h, BUILD-AND-RUN.md, layouts, vectors.json, model files."
echo "The file that unblocked us: tools/llama2c/BUILD-AND-RUN.md (gave exact build and run commands)."
echo "Compiler used: $COMPILER"
echo "Build command: $BUILD_CMD"
echo "Runner invocations:"
echo "  ./run.exe model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i \"Once upon a time\""
echo "  ./run.exe model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 32 -i \"The little robot\""
echo "Prediction: as above from vectors.json."
echo "Actual output: see above."
echo "Verification verdict: see above."

exit 0
