import zipfile
import os

def print_file_contents(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Get all Python files
        python_files = [f for f in zip_ref.namelist() if f.endswith('.py')]

        # Sort files to maintain consistent order
        python_files.sort()

        # Create a markdown file
        with open('project_contents.md', 'w', encoding='utf-8') as output:
            for file_path in python_files:
                # Add file header
                output.write(f"\n### `{file_path}`\n\n")
                output.write("```python\n")

                try:
                    # Read and decode the file content
                    content = zip_ref.read(file_path).decode('utf-8')
                    output.write(content)
                except Exception as e:
                    output.write(f"# Error reading file: {str(e)}")

                output.write("\n```\n")

# Execute
print_file_contents('mtg-db-lorcana.zip')
print("File 'project_contents.md' has been created with all Python file contents.")