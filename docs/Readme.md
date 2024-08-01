# Project Documentation

This project uses Sphinx to generate documentation from OpenAPI JSON files and other sources. Follow the instructions below to build and view the documentation.

## Generating Documentation

To generate the current documentation, follow these steps:

1. Install the requirements present in `requirements.txt`.
2. Open a terminal in the root directory of the project and go to `docs/` directory
3. Run the following command to build the documentation:

   ```sh
   make html SPHINXOPTS="-v"

## Viewing Documentation

After building the documentation, you can view the generated HTML files:

1. Navigate to the `build/html` directory in your terminal or file explorer.
2. Open the `index.html` file in your preferred web browser.

### Using the Command Line (Optional)

- On macOS:
  ```sh
  open build/html/index.html

- On Linux:
  ```sh
  xdg-open build/html/index.html

- On windows:
  ```sh
  start build/html/index.html


## Adding or Modifying `openapi.json`

### Adding a New `openapi.json` File

1. **Generate the `openapi.json` file:**
   - Run your FastAPI application and navigate to `{your_endpoint}/openapi.json` to download the `openapi.json` file.

2. **Place the `openapi.json` file:**
   - Save the `openapi.json` file in the root directory of your documentation project. Look for already existing files in `docs/`

3. **Create a corresponding `.rst` file:**
   - Create a new reStructuredText (`.rst`) file in the `source` directory.
   - Name it appropriately, for example, `new_endpoint.rst`.

4. **Add the `openapi.json` directive:**
   - In the new `.rst` file, add the following content:
     ```rst
     .. openapi:: new_openapi.json
     ```

5. **Update the `index.rst` file:**
   - Open `source/index.rst` and add a reference to the new `.rst` file:
     ```rst
     .. toctree::
        :maxdepth: 2
        :caption: Contents:

        new_endpoint
     ```

### Modifying an Existing `openapi.json` File

1. **Generate the updated `openapi.json` file:**
   - Run your FastAPI application and navigate to `{your_endpoint}/openapi.json` to download the updated `openapi.json` file.

2. **Replace the old `openapi.json` file:**
   - Save the updated `openapi.json` file, replacing the old file in the root directory of your documentation project.

3. **Rebuild the documentation:**
   - Run the following command to rebuild the HTML documentation:
     ```sh
     make html SPHINXOPTS="-v"
     ```

4. **View the updated documentation:**
   - Navigate to the `build/html` directory and open the `index.html` file in your preferred web browser.
