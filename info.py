import os

def print_tree(root_dir, output_file=None, sample_files=5):
    tree_lines = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        depth = dirpath.replace(root_dir, "").count(os.sep)
        indent = "    " * depth
        tree_lines.append(f"{indent}{os.path.basename(dirpath)}/")

        # Only show up to sample_files files
        for f in filenames[:sample_files]:
            tree_lines.append(f"{indent}    {f}")

        # If more files exist, show summary
        if len(filenames) > sample_files:
            tree_lines.append(f"{indent}    [+ {len(filenames) - sample_files} more files]")

    tree_text = "\n".join(tree_lines)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(tree_text)
        print(f"[+] Project structure saved to {output_file}")
    else:
        print(tree_text)


if __name__ == "__main__":
    project_path = r"D:\CultureCircle-Scraper\CultureCircle-Scraper"  # 👈 replace with your project folder
    output_path = "project_structure.txt"
    print_tree(project_path, output_file=output_path, sample_files=5)
