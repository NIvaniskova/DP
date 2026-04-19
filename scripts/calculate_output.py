import numpy as np
import csv
import os
import re

GATE_PATTERN = re.compile(r"\(\[(\d+)\](\d+),(\d+),(\d+)\)")
OUTPUTS_PATTERN = re.compile(r"\((-?\d{1,3}(?:,-?\d{1,3})*)\)$")  
 

# 1. Pre-compute the Golden Model (256x256 grid)
val = np.arange(256, dtype=np.uint32)
A, B = np.meshgrid(val, val)
golden = A * B
mask = golden > 0

def evaluate_cgp(chr_file, A_grid, B_grid):
    """Parses .chr logic and returns a 256x256 uint32 result."""
    try:
        with open(chr_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except IOError as e:
        print(f"Error reading file {chr_file}: {e}")
        return None 
    
    # Process content - get last line
    lines = content.strip().splitlines()
    if not lines:
        print(f"{chr_file} has no valid lines.")
        return None 
    last_line = lines[-1]
    last_line_clean = last_line
    if last_line.startswith("{"):
        closing_brace = last_line.find("}")
        if closing_brace != -1:
            # process metadata
            metadata_raw = last_line[1: closing_brace]
            metadata = metadata_raw.split(",")
            all_gates = metadata[2]
            # remove metadata from last line
            last_line_clean = last_line[closing_brace + 1:]
        else:
            print(f"Malformed file: {chr_file}.")
            return None
        
    # Extract output gates    
    outputs_match = OUTPUTS_PATTERN.search(last_line_clean)
    if not outputs_match:
        print(f"No output gates found in {chr_file}.")
        return None    
    output_gates = [int(x) for x in outputs_match.group(1).split(",")]
    gates_line = last_line_clean[:outputs_match.start()]
    
    # Parse all gates
    matches = GATE_PATTERN.findall(gates_line)
    if not matches:
        print(f"No gates found in {chr_file}.")
        return None
    
    gates = {}
    for m in matches:
        gate_id, in_1, in_2, function_id = map(int, m)
        gates[gate_id] = (in_1, in_2, function_id)

    # Evaluate gates in order (assuming they are topologically sorted)
    nodes = {}
    for g_id in sorted(gates.keys()):
        in_1, in_2, f = gates[g_id]
        src1 = A_grid if in_1 == -1 else (B_grid if in_1 == -2 else nodes.get(in_1, np.zeros_like(A_grid)))
        src2 = A_grid if in_2 == -1 else (B_grid if in_2 == -2 else nodes.get(in_2, np.zeros_like(A_grid)))

        # Standard CGP Function Set (Adjust if yours differs!)
        if f == 0: res = src1                 # IDA 
        elif f == 1: res = 1 - src1             # INVA
        elif f == 2: res = src1 & src2          # AND
        elif f == 3: res = src1 | src2          # OR
        elif f == 4: res = src1 ^ src2          # XOR
        elif f == 5: res = 1 - (src1 & src2)    # NAND
        elif f == 6: res = 1 - (src1 | src2)    # NOR
        elif f == 7: res = 1 - (src1 ^ src2)    # XNOR
        nodes[g_id] = res

    # Extract output indices from the trailing parentheses: (8,9,...)
    output_match = re.search(r"\(([\d,]+)\)$", chr_file)
    if not output_match:
        return np.zeros_like(A_grid)
    
    output_indices = [int(x) for x in output_match.group(1).split(',')]
    
    # Stitch bits back together (O15 is index 0, O0 is index 15 usually in .chr)
    final_output = np.zeros_like(A_grid, dtype=np.uint32)
    for i, node_idx in enumerate(reversed(output_indices)):
        final_output |= (nodes[node_idx].astype(np.uint32) << i)
        
    return final_output

def calculate_metrics(approx_results, golden, mask, m_id):
    error_map = np.abs(golden.astype(np.int32) - approx_results.astype(np.int32))
    mae = np.mean(error_map)
    wce = np.max(error_map)
    wcre = np.max(error_map[mask] / golden[mask])
    return [m_id, mae, wce, wcre]

# --- Execution Loop ---
input_folder = "../test_data/"
results_summary = []

# Filter for .chr files and sort them
files = [f for f in os.listdir(input_folder) if f.endswith('.chr')]
files.sort()

print(f"Starting analysis on {len(files)} multipliers...")

for filename in files:
    with open(os.path.join(input_folder, filename), 'r') as f:
        content = f.read().strip()

    # Print filename
    print(f"Processing: {filename}")
    
    # Calculate approx output
    approx_output = evaluate_cgp(content, A, B)
    
    # Calculate metrics
    metrics = calculate_metrics(approx_output, golden, mask, filename)
    results_summary.append(metrics)
    
    if len(results_summary) % 500 == 0:
        print(f"Progress: {len(results_summary)}/{len(files)} processed.")

# Save results
os.makedirs("../files/", exist_ok=True)
with open("../files/multiplier_errors.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Filename", "MAE", "WCE", "WCRE"])
    writer.writerows(results_summary)

print("Analysis complete. Results saved to ../files/multiplier_errors.csv")