import os
import re
import argparse
import csv

GATE_PATTERN = re.compile(r"\(\[(\d+)\](\d+),(\d+),(\d+)\)")
OUTPUTS_PATTERN = re.compile(r"\((-?\d{1,3}(?:,-?\d{1,3})*)\)$")  
      

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
            used.add(current)
            continue

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
    
    #print(len(all_rows))

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
    
    suffix = ".chr"
    if chr_file.endswith(suffix):
        file_name = chr_file[: -len(suffix)]
    file_name = file_name.split("\\")[-1]

    used_gate_details = [([gid], *gates[gid]) for gid in sorted(used) if gid in gates]

    row = f"{file_name} ; {all_gates} ; {used_gate_details} ; {list(output_gates)}"

    return row



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

    # Process files one by one and write results one by one to txt file 
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            
            cnt = 0
            for entry in os.scandir(input_folder):
                cnt += 1
                if entry.is_file():
                    file_path = entry.path
                    
                    row = process_chr_file(file_path)
                    
                    if row is not None:
                        outfile.write(row + "\n")
                    else:
                        print(f"File could not be processed: {file_path}")

                if cnt % 100 == 0:
                    print(f"Processed {cnt} files...")
    
    except IOError as e:
        print(f"Error writing to file {output_file}: {e}")

        



if __name__ == "__main__":

    main()