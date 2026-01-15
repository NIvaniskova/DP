import json
import csv
import argparse
import os


# Load JSON data from a file
def load_json(json_file):
    print(f"Loading JSON data from {json_file}...")
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data


# Get multiple feature values (in order) from all components
def get_values(data, feature_names):
    results = {}

    for component_name, component in data.items():
        values = []
        for feature in feature_names:
            value = component.get(feature)
            if value is None:
                print(f"Feature '{feature}' not found in component '{component_name}'.")
            values.append(value)
        results[component_name] = values

    return results


def get_levels(data):
    levels = {}

    for component_name, component in data.items():
        level = component["evo"]["Levels"] if "evo" in component else None
        if level is None:
            print(f"'levels' not found in component '{component_name}'.")
        levels[component_name] = level

    return levels



# Save feature values to a CSV file
def save_features_to_file(values, output_file, header):
    
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for component, values in values.items():
            writer.writerow([component] + values)

    print(f"Saved results to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="process file input and output paths"
    )

    parser.add_argument(
        "input",
        type=str,
        help="path to input JSON file"
    )

    parser.add_argument(
        "output",
        type=str,
        help="path to output CSV file"
    )

    args = parser.parse_args()

    json_file = args.input
    output_file = args.output

    data = load_json(json_file)
    
    feature_names = ["cells", "seed", "mae", "wce", "wcre%"]
    header = ["Name"] + feature_names + ["Levels"]

    values = get_values(data, feature_names)
    levels = get_levels(data)
    for component in values:
        values[component].append(levels.get(component, "N/A"))
    
    save_features_to_file(values, output_file, header)


if __name__ == "__main__":
    main()

