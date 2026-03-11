from ast import pattern
import re
import csv
from collections import Counter, defaultdict
import collections
import argparse
import ast


pattern = re.compile(r'\(\[(\d+)\],\s*(\d+),\s*(\d+),\s*(\d+)\)')

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


def calculate_longest_path(gates, output_gates_int):
    max_id = max(gates.keys())
    delay = [1] * (max_id + 1)

    sorted_used = sorted(gates.keys())

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

    po_delays = [delay[po_index] + 1 for po_index in output_gates_int]
    longest_path_value = max(po_delays) if po_delays else 0  

    return longest_path_value


def get_level(gid, gates, gate_levels, num_primary_inputs):
    # Primary inputs (0-15) have a depth of 0
    if gid < num_primary_inputs:
        return 0
    if gid in gate_levels:
        return gate_levels[gid]
    
    if gid in gates:
        in1, in2, func_id = gates[gid]
        w = WEIGHTS.get(func_id, 2)
        if func_id <= 1:  
            level = w + get_level(in1, gates, gate_levels, num_primary_inputs)
        else:
            level = w + max(get_level(in1, gates, gate_levels, num_primary_inputs), get_level(in2, gates, gate_levels, num_primary_inputs))
        gate_levels[gid] = level
        return level
    return 0


def main():
    parser = argparse.ArgumentParser(description="Extract gate information from CSV files.")
    parser.add_argument("input_file", help="Path to the input TXT file.")
    parser.add_argument("output_file", help="Path to the output CSV file.")
    args = parser.parse_args()

    print(f"Reading from {args.input_file}...")
    print(f"Writing to {args.output_file}...")

    with open(args.input_file, 'r') as infile, open(args.output_file, 'w', newline='') as csvfile:

        writer = csv.writer(csvfile)
        HEADER = ["NAME","ALL_GATES","USED_GATES"] + [name for name in FUNCTION_MAP.values()] + ["TOTAL_AREA", "LONGEST PATH", "SHARING_FACTOR", "WSS", "LSB%", "MSB%", "GLOBAL_MAX_DEPTH", "MSB_MAX_DEPTH", "MAX_FANOUT", "GATES_FANOUT_GT_3", "MAX_WIDTH", "DEPTH_SKEW", "CONGESTION_INDEX"]
        writer.writerow(HEADER) 

        cnt = 0
        for line in infile:
            cnt += 1
            line = line.strip()
            if not line:
                continue

            # Extract the file name and gate information
            line_parts = line.split(';')
            if len(line_parts) < 4:
                print(f"Skipping malformed line: {line}")
                continue
            file_name = line_parts[0].strip()
            #print(f"Processing line: {file_name}")

            all_gates = int(line_parts[1].strip())
            gate_info = line_parts[2].strip()
            output_gates = line_parts[3].strip()
            output_gates_int = ast.literal_eval(output_gates)

            gates = {}
            matches = pattern.findall(gate_info)
            for m in matches:
                gate_id, in_1, in_2, function_id = map(int, m)
                gates[gate_id] = (in_1, in_2, function_id)
            if not gates:
                continue


            # 1. COUNT USED GATES
            total_used_gates = len(gates)
            
            # 2. COUNT GATES BY FUNCTION
            used_function_ids = [gates[gate_id][2] for gate_id in gates]
            gates_counts = Counter(used_function_ids)

            # For gates NOR, XNOR, NAND inlcude inverter into total gates count
            for fid in [5, 6, 7]:  # NAND2, NOR2, XNOR2
                if fid in gates_counts:
                    gates_counts[1] += gates_counts[fid]  # Add to INVA count
                    total_used_gates += gates_counts[fid]  # Increase total used gates


            # 3. CALCULATE TOTAL AREA
            total_area = sum(AREA_MAP[FUNCTION_MAP[fun_id]] for _, _, fun_id in gates.values())


            # 4. CALCULATE LONGEST PATH
            longest_path = calculate_longest_path(gates, output_gates_int)
            longest_path_value = longest_path if longest_path is not None else 0

            
            # Calculate which gates influence which output bits
            gates_influence = defaultdict(set)
            for po_index, gate_id in enumerate(output_gates_int):
                for used_gate in gates:
                    if used_gate == gate_id:
                        gates_influence[used_gate].add(po_index)
                    else:   
                        stack = [gate_id]
                        visited = set()
                        while stack:
                            current = stack.pop()
                            if current in visited:
                                continue
                            visited.add(current)
                            if current == used_gate:
                                gates_influence[used_gate].add(po_index)
                                break
                            if current in gates:
                                in_1, in_2, _ = gates[current]
                                if in_1 >= 0:
                                    stack.append(in_1)
                                if in_2 >= 0:
                                    stack.append(in_2)
           
            # 5. CALCULATE SHARING FACTOR
            sf = 0
            for gate_id in sorted(gates_influence):
                sf += len(gates_influence[gate_id])
            sf = sf / total_used_gates if total_used_gates > 0 else 0

            # Calculate levels for all used gates
            gate_levels = {}
            num_primary_inputs = 16 
            for gid in gates:
                get_level(gid, gates, gate_levels, num_primary_inputs)

            # 6. CALCULATE MAX DEPTH PER OUTPUT BIT
            max_depth_per_bit = {i: 0 for i in range(16)}
            for gid, influenced_bits in gates_influence.items():
                d = gate_levels.get(gid, 0)
                for bit in influenced_bits:
                    if d > max_depth_per_bit[bit]:
                        max_depth_per_bit[bit] = d

            # 7. CALCULATE GLOBAL MAX DEPTH, MSB MAX DEPTH, LSB MAX DEPTH
            global_max_depth = max(max_depth_per_bit.values())
            msb_max_depth = max(max_depth_per_bit[b] for b in range(12, 16)) 
            #lsb_max_depth = max(max_depth_per_bit[b] for b in range(0, 4))   

            # 8. CALCULATE WSS AND ZONAL BIN COUNTS
            # WSS is the sum of 2^bit for all bits influenced by a gate, summed over all gates
            lsb_count = 0  # Bits 0-3
            mid_count = 0  # Bits 4-11
            msb_count = 0  # Bits 12-15
            wss_score = 0  # Weighted Significance Score

            for gate_id, influenced_bits in gates_influence.items():
                # A. Calculate WSS: Sum of 2^bit for all bits this gate touches
                gate_weight = sum(2**bit for bit in influenced_bits)
                wss_score += gate_weight
                
                # B. Assign to Zonal Bins (a gate can belong to multiple)
                if any(0 <= b <= 3 for b in influenced_bits):
                    lsb_count += 1
                if any(4 <= b <= 11 for b in influenced_bits):
                    mid_count += 1
                if any(12 <= b <= 15 for b in influenced_bits):
                    msb_count += 1

            # Calculate percentages for LSB and MSB bins
            lsb_perc = lsb_count / total_used_gates if total_used_gates > 0 else 0
            msb_perc = msb_count / total_used_gates if total_used_gates > 0 else 0


            # 9. CALCULATE FAN-OUT METRICS
            # Count how many times each gate is used as an input by another gate
            all_inputs = []
            for inputs in gates.values():
                all_inputs.extend(inputs)
            
            fanout_counts = collections.Counter(all_inputs)
            
            if fanout_counts:
                max_fanout = max(fanout_counts.values())
                count_gates_fanout_gt_3 = sum(1 for count in fanout_counts.values() if count > 3)
            else:
                max_fanout = 0
                count_gates_fanout_gt_3 = 0

            # 10. CALCULATE MAX WIDTH 
            # (Max gates at any logical depth)
            if gate_levels:
                level_counts = collections.Counter(gate_levels.values())
                max_width = max(level_counts.values())
            else:
                max_width = 0

            # 11. CALCULATE DEPTH SKEW 
            # (Difference in max depth between LSB and MSB paths)
            lsb_depths = []
            msb_depths = []

            for gate_id, bits in gates_influence.items():
                level = gate_levels.get(gate_id, 0)
                if any(b <= 3 for b in bits):
                    lsb_depths.append(level)
                if any(b >= 12 for b in bits):
                    msb_depths.append(level)

            max_lsb = max(lsb_depths) if lsb_depths else 0
            max_msb = max(msb_depths) if msb_depths else 0
            
            depth_skew = max_msb - max_lsb


            # 12. CONGESTION INDEX (High participation gates)
            # Gates that influence more than 40% of the total output bits
            high_participation = sum(1 for bits in gates_influence.values() if len(bits) > 6)
            congestion_index = high_participation

            
            #print(f"File: {file_name}, Total Gates: {all_gates}, Used Gates: {total_used_gates}, Total Area: {total_area:.4f}, Longest Path: {longest_path_value}, Sharing Factor: {sf:.4f}, WSS: {wss_score}, LSB%: {lsb_perc:.4f}, MSB%: {msb_perc:.4f}, Global Max Depth: {global_max_depth}, MSB Max Depth: {msb_max_depth}, Max Fan-out: {max_fanout}, Gates with Fan-out > 3: {count_gates_fanout_gt_3}, Max Width: {max_width}, Depth Skew: {depth_skew}, Congestion Index: {congestion_index}")


            row = [file_name]
            row.append(all_gates)
            row.append(total_used_gates)
            for function_id in sorted(FUNCTION_MAP):
                row.append(gates_counts.get(function_id, 0))
            row.append(f"{total_area:.4f}")
            row.append(longest_path_value)
            row.append(f"{sf:.4f}")
            row.append(wss_score)
            row.append(f"{lsb_perc:.4f}")
            row.append(f"{msb_perc:.4f}")
            row.append(global_max_depth)
            row.append(msb_max_depth)
            row.append(max_fanout)
            row.append(count_gates_fanout_gt_3)
            row.append(max_width)
            row.append(depth_skew)
            row.append(congestion_index)





            # Write to CSV file
            writer.writerow(row)

            if cnt%100 == 0:
                print(f"Processed {cnt} lines...")



    







if __name__ == "__main__":

    main()