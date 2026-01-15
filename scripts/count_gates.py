import os
import re
import csv
from collections import Counter
import argparse

GATE_PATTERN = re.compile(r"\(\[(\d+)\](\d+),(\d+),(\d+)\)")
OUTPUTS_PATTERN = re.compile(r"\((-?\d{1,3}(?:,-?\d{1,3})*)\)$")  

FUNCTION_MAP = {
    0: "IDA",
    1: "INVA",
    2: "AND2",
    3: "OR2",
    4: "XOR2",
    5: "NAND2",
    6: "NOR2",
    7: "XNOR2"
}

AREA_MAP = {
    "NONE": 0.0,
    "INVA": 1.4, 
    "AND2": 2.34,
    "NAND2": 1.87, 
    "OR2": 2.34,
    "XOR2": 4.69,
    "NOR2": 2.34, 
    "XNOR2": 4.69
}     


WEIGHTS = {
        0: 0,  # IDA
        1: 1,  # INVA
        2: 1,  # AND2
        3: 1,  # OR2
        4: 1,  # XOR2
        5: 1,  # NAND2
        6: 1,  # NOR2
        7: 1   # XNOR2
    }
        


def count_used_gates(gates, output_gates):
    used = set()
    stack = [(g, False) for g in output_gates if g >= 0]  # (node, visited_flag)

    while stack:
        current, visited_flag = stack.pop()

        if current in (None, -1):
            continue
        if current not in gates:
            continue

        if visited_flag:
            # Post-order: add node after all inputs processed
            used.add(current)
            continue

        # Push the node back with visited_flag=True to process after inputs
        stack.append((current, True))

        in_1, in_2, fun = gates[current]
        if fun == 0 or fun == 1:
            if in_1 in gates and in_1 not in used:
                stack.append((in_1, False))
        else:
            for inp in (in_1, in_2):
                if inp in gates and inp not in used:
                    stack.append((inp, False))
    
    return used





def calculate_all_rows(input_folder):

    all_rows = []

    if not os.path.isdir(input_folder):
        print(f"Error: Input folder not found at '{input_folder}'")
        return all_rows  # Empty list
    
    for entry in os.scandir(input_folder):
        if entry.is_file():
            file_path = entry.path
            
            row = process_chr_file(file_path)
            
            if row is not None:
                all_rows.append(row)
            else:
                print(f"File could not be processed: {file_path}")
    
    print(len(all_rows))

    return all_rows


def process_chr_file(chr_file):
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

    # Count used gates
    used = count_used_gates(gates, output_gates)
    

    # Count number of each function ID
    used_function_ids = [gates[gate_id][2] for gate_id in used]
    gates_counts = Counter(used_function_ids)
    total_used_gates = len(used)


    # Calculate longest path
    max_id = max(max(gates.keys()), max(output_gates))
    delay = [1] * (max_id + 1)

    sorted_used = sorted(used)

    for gate_id in sorted_used:
        in_1, in_2, func_id = gates[gate_id]
        
        d1 = delay[in_1]
        
        if func_id > 1:  # Binary gates (AND, OR, XOR...)
            d2 = delay[in_2]
            # Max of inputs + gate weight
            delay[gate_id] = max(d1, d2) + WEIGHTS[func_id]
        else:           # Unary gates (IDA, INVA)
            # Only first input matters
            delay[gate_id] = d1 + WEIGHTS[func_id]

    po_delays = [delay[po_index] + 1 for po_index in output_gates]
    longest_path_value = max(po_delays) if po_delays else 0


    # For gates NOR, XNOR, NAND inlcude inverter into total gates count
    for fid in [5, 6, 7]:  # NAND2, NOR2, XNOR2
        if fid in gates_counts:
            gates_counts[1] += gates_counts[fid]  # Add to INVA count
            total_used_gates += gates_counts[fid]  # Increase total used gates

    

    # Calculate total area
    total_area = 0.0
    for fid, count in gates_counts.items():
        gate_name = FUNCTION_MAP.get(fid, None)
        if gate_name and gate_name in AREA_MAP:
            total_area += AREA_MAP[gate_name] * count

    # Prepare row data
    row = []
    suffix = ".chr"
    if chr_file.endswith(suffix):
        file_name = chr_file[: -len(suffix)]
    file_name = file_name.split("\\")[-1]

    # all_gates from metadata
    # total_used_gates calculated from used set
    row = [file_name, all_gates, total_used_gates]
    
    for function_id in sorted(FUNCTION_MAP):
        row.append(gates_counts.get(function_id, 0))
        

    # Add total area (formatted to 4 decimal places)
    row.append(longest_path_value)
    row.append(f"{total_area:.4f}")


    return row


def write_output_file(data_rows, output_file):
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            
            HEADER = ["NAME", "ALL_GATES", "USED_GATES"] + [name for name in FUNCTION_MAP.values()] + ["LONGEST PATH", "TOTAL_AREA"]
            writer.writerow(HEADER) 
            
            writer.writerows(data_rows)
            
        print(f"Success: Wrote {len(data_rows)} rows to '{output_file}'")
        
    except IOError as e:
        print(f"Error writing to file {output_file}: {e}")


def main():

    parser = argparse.ArgumentParser(description="Count gates in .chr files and output to CSV.")
    parser.add_argument(
        "input",
        type=str,
        help="path to input folder"
    )

    parser.add_argument(
        "output",
        type=str,
        help="path to output CSV file"
    )
    args = parser.parse_args()
    input_folder = args.input
    output_file = args.output

    # Calculate the data by processing all files
    data_to_write = calculate_all_rows(input_folder)
    
    #  Write the output file
    if data_to_write:
        write_output_file(data_to_write, output_file)
    else:
        print("No data calculated to write.")



if __name__ == "__main__":

    main()