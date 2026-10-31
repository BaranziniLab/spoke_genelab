import os
import sys
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv
import papermill as pm
import subprocess
import neo4j_utils


def import_from_csv_to_neo4j_community(verbose=False):
    setup()
    pm.execute_notebook(
        "PrepareNeo4jBulkImport.ipynb", "PrepareNeo4jBulkImport_out.ipynb"
    )
    run_bulk_import(verbose=verbose)
    neo4j_utils.start()
    add_indices(verbose=verbose)


def import_from_csv_to_neo4j_desktop(verbose=False):
    setup()
    drop_database(verbose=verbose)
    pm.execute_notebook(
        "PrepareNeo4jBulkImport.ipynb", "PrepareNeo4jBulkImport_out.ipynb"
    )
    run_bulk_import(verbose=verbose)
    create_database(verbose=verbose)
    add_indices(verbose=verbose)


def import_from_csv_to_neo4j_enterprise(verbose=False):
    setup()
    run_cypher("pre", verbose=verbose)
    drop_database(verbose=verbose)
    pm.execute_notebook(
        "PrepareNeo4jBulkImport.ipynb", "PrepareNeo4jBulkImport_out.ipynb"
    )
    run_bulk_import(verbose=verbose)
    create_database(verbose=verbose)
    add_indices(verbose=verbose)
    run_cypher("post", verbose=verbose)


def setup():
    load_dotenv("../.env", override=True)
    # Check environment variables and directory structure
    NEO4J_HOME = os.getenv("NEO4J_HOME")
    if not NEO4J_HOME:
        sys.exit("NEO4J_HOME environment variable has not been set")
    if not os.path.exists(NEO4J_HOME):
        sys.exit(f"Neo4j HOME directory not found: {NEO4J_HOME}")

    NEO4J_BIN = os.getenv("NEO4J_BIN")
    if not NEO4J_BIN:
        sys.exit("NEO4J_BIN environment variable has not been set")
    if not os.path.exists(NEO4J_BIN):
        sys.exit(f"NEO4J_BIN directory not found: {NEO4J_BIN}")

    NEO4J_IMPORT = os.path.join(NEO4J_HOME, "import")
    if not os.path.exists(NEO4J_IMPORT):
        sys.exit(f"Neo4j import directory not found: {NEO4J_IMPORT}")

    NEO4J_METADATA = os.getenv("NEO4J_METADATA")
    if not os.path.exists(NEO4J_METADATA):
        sys.exit(f"Metadata directory not found: {NEO4J_METADATA}")

    NEO4J_METADATA_NODES = os.path.join(NEO4J_METADATA, "nodes")
    if not os.path.exists(NEO4J_METADATA_NODES):
        sys.exit(f"Metadata directory not found: {NEO4J_METADATA_NODES}")

    NEO4J_METADATA_RELATIONSHIPS = os.path.join(NEO4J_METADATA, "relationships")
    if not os.path.exists(NEO4J_METADATA_RELATIONSHIPS):
        sys.exit(f"Metadata directory not found: {NEO4J_METADATA_RELATIONSHIPS}")

    NEO4J_DATA = os.getenv("NEO4J_DATA")
    if not os.path.exists(NEO4J_DATA):
        sys.exit(f"Data directory not found: {NEO4J_DATA}")

    NEO4J_DATA_NODES = os.path.join(NEO4J_DATA, "nodes")
    if not os.path.exists(NEO4J_DATA_NODES):
        sys.exit(f"Data directory not found: {NEO4J_DATA_NODES}")

    NEO4J_DATA_RELATIONSHIPS = os.path.join(NEO4J_DATA, "relationships")
    if not os.path.exists(NEO4J_DATA_RELATIONSHIPS):
        sys.exit(f"Data directory not found: {NEO4J_DATA_RELATIONSHIPS}")

    # Clean import directory

    for file in Path(NEO4J_IMPORT).glob("*.csv"):
        os.remove(file)

    # args.txt contains arguments for the neo4j_admin tool
    if os.path.exists(os.path.join(NEO4J_IMPORT, "args.txt")):
        os.remove(os.path.join(NEO4J_IMPORT, "args.txt"))

    if os.path.exists(os.path.join(NEO4J_IMPORT, "indices.cypher")):
        os.remove(os.path.join(NEO4J_IMPORT, "indices.cypher"))

    if os.path.exists(os.path.join(NEO4J_IMPORT, "import.report")):
        os.remove(os.path.join(NEO4J_IMPORT, "import.report"))

    # Copy data and metadata files into the import directory
    # The header line is removed since the column names and types are provided in a separate file for bulk download.

    for input_file in Path(NEO4J_DATA_NODES).glob("*.csv"):
        output_file = os.path.join(NEO4J_IMPORT, f"{input_file.stem}_n.csv")
        copy_without_header(input_file, output_file)

    for input_file in Path(NEO4J_DATA_RELATIONSHIPS).glob("*.csv"):
        output_file = os.path.join(NEO4J_IMPORT, f"{input_file.stem}_r.csv")
        copy_without_header(input_file, output_file)


def copy_without_header(input_file, output_file):
    with open(input_file, "r") as f_in, open(output_file, "w") as f_out:
        next(f_in)  # Skip the first line
        shutil.copyfileobj(f_in, f_out)


def quote_path(path):
    if " " in path:
        return f"'{path}'"
    return path


def dump_database(verbose=False):
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
    NEO4J_INSTALL_PATH = os.getenv("NEO4J_INSTALL_PATH")
    neo4j_dump = os.path.join(NEO4J_INSTALL_PATH, version)
    NEO4J_BIN = os.getenv("NEO4J_BIN")
    neo4j_admin = quote_path(os.path.join(NEO4J_BIN, "neo4j-admin"))

    os.makedirs(neo4j_dump, exist_ok=True)
    neo4j_dump = quote_path(eo4j_dump)
    command = f"{neo4j_admin} database dump {NEO4J_DATABASE} --to-path={neo4j_dump}"

    if verbose:
        print(f"dump_database: {command}", flush=True)

    try:
        ret = subprocess.run(command, capture_output=True, check=True, shell=True)
        if verbose:
            print(ret.stdout.decode(), flush=True)
        print(f"{NEO4J_DATABASE} dumped to: {neo4j_dump}")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: dump_database: Dump failed for database: {NEO4J_DATABASE}")
        print(e.output)
        raise
    if verbose:
        print(ret.stdout.decode())


def drop_database(verbose=False):
    NEO4J_HOME = os.getenv("NEO4J_HOME")
    NEO4J_BIN = os.getenv("NEO4J_BIN")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

    # Cypher-shell requires database names to be quoted by tick marks if non-alphanumeric characters are in the name.
    NEO4J_DATABASE_QUOTED = f"`{NEO4J_DATABASE}`"

    cypher_shell = quote_path(os.path.join(NEO4J_BIN, "cypher-shell"))
    command = f"{cypher_shell} -d system -u {NEO4J_USERNAME} -p {NEO4J_PASSWORD} 'DROP DATABASE {NEO4J_DATABASE_QUOTED} IF EXISTS WAIT;'"
    if verbose:
        print(f"drop_database: {command}", flush=True)

    try:
        ret = subprocess.run(command, capture_output=True, check=True, shell=True)
        if verbose:
            print(ret.stdout.decode(), flush=True)
    except subprocess.CalledProcessError as e:
        print(
            f"ERROR: drop_database: The Graph DBMS is not running or the database name: {NEO4J_DATABASE}, username: {NEO4J_USERNAME}, or password: {NEO4J_PASSWORD} are incorrect. Start the Graph DBMS before running this script.",
            flush=True,
        )
        print(e.output)
        raise

    # remove the database file
    # TODO remove the transaction files as well
    database_dir = os.path.join(NEO4J_HOME, "data", "databases", NEO4J_DATABASE)
    shutil.rmtree(database_dir, ignore_errors=True)


def run_bulk_import(verbose=False):
    NEO4J_HOME = os.getenv("NEO4J_HOME")
    NEO4J_IMPORT = os.path.join(NEO4J_HOME, "import")
    NEO4J_BIN = os.getenv("NEO4J_BIN")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
    NEO4J_ADMIN_JAVA_OPTS = os.getenv("NEO4J_ADMIN_JAVA_OPTS")

    # run import
    neo4j_admin = quote_path(os.path.join(NEO4J_BIN, "neo4j-admin"))
    NEO4J_IMPORT = quote_path(NEO4J_IMPORT)
#     command = f"export NEO4J_ADMIN_JAVA_OPTS='{NEO4J_ADMIN_JAVA_OPTS}'; cd {NEO4J_IMPORT}; {neo4j_admin} database import full {NEO4J_DATABASE} --overwrite-destination --skip-bad-relationships --skip-duplicate-nodes --array-delimiter='|' @args.txt"
    command = f"export NEO4J_ADMIN_JAVA_OPTS='{NEO4J_ADMIN_JAVA_OPTS}'; cd {NEO4J_IMPORT}; {neo4j_admin} database import full {NEO4J_DATABASE} --overwrite-destination --skip-bad-relationships --skip-duplicate-nodes --max-off-heap-memory=8g --array-delimiter='|' @args.txt"

    if verbose:
        print(f"run_bulk_import: {command}", flush=True)

    try:
        ret = subprocess.run(command, capture_output=True, check=True, shell=True)
        if verbose:
            print(ret.stdout.decode(), flush=True)
    except subprocess.CalledProcessError as e:
        print(
            f"ERROR: run_bulk_import: The import failed for database: {NEO4J_DATABASE}",
            flush=True,
        )
        print(e.output)
        raise


def create_database(verbose=False):
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    NEO4J_BIN = os.getenv("NEO4J_BIN")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
    # Cypher-shell requires database names to be quoted by tick marks if non-alphanumeric characters are in the name.
    NEO4J_DATABASE_QUOTED = f"`{NEO4J_DATABASE}`"

    # compose the cypher shell command
    cypher_shell = quote_path(os.path.join(NEO4J_BIN, "cypher-shell"))
    command = f"{cypher_shell} -d system -u {NEO4J_USERNAME} -p {NEO4J_PASSWORD} 'CREATE OR REPLACE DATABASE {NEO4J_DATABASE_QUOTED} WAIT;'"
    if verbose:
        print(f"create_database: {command}", flush=True)

    # run command to create the database
    try:
        ret = subprocess.run(command, capture_output=True, check=True, shell=True)
        if verbose:
            print(ret.stdout.decode(), flush=True)
    except subprocess.CalledProcessError as e:
        print(
            f"ERROR: create_database: The Graph DBMS is not running or the database name: {NEO4J_DATABASE}, username: {NEO4J_USERNAME}, or password: {NEO4J_PASSWORD} are incorrect.",
            flush=True,
        )
        print(e.output)
        raise


def add_indices(verbose=False):
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    NEO4J_HOME = os.getenv("NEO4J_HOME")
    NEO4J_IMPORT = os.path.join(NEO4J_HOME, "import")
    NEO4J_BIN = os.getenv("NEO4J_BIN")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
    # Cypher-shell requires database names to be quoted by tick marks if non-alphanumeric characters are in the name.
    NEO4J_DATABASE_QUOTED = f"`{NEO4J_DATABASE}`"

    # compose the cypher shell command
    cypher_shell = quote_path(os.path.join(NEO4J_BIN, "cypher-shell"))
    cypher_script = quote_path(os.path.join(NEO4J_IMPORT, "indices.cypher"))
    command = f"{cypher_shell} -d {NEO4J_DATABASE} -u {NEO4J_USERNAME} -p {NEO4J_PASSWORD} -f {cypher_script}"

    if verbose:
        print(f"add_indices: {command}", flush=True)

    # run command to add the indices and constraints
    try:
        ret = subprocess.run(command, capture_output=True, check=True, shell=True)
        if verbose:
            print(ret.stdout.decode(), flush=True)
    except subprocess.CalledProcessError as e:
        print("ERROR: add_indices: adding indices and constraints failed.", flush=True)
        print(e.output)
        raise


def run_cypher(mode, verbose=False):
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    NEO4J_BIN = os.getenv("NEO4J_BIN")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
    # Cypher-shell requires database names to be quoted by tick marks if non-alphanumeric characters are in the name.
    NEO4J_DATABASE_QUOTED = f"`{NEO4J_DATABASE}`"

    if mode == "pre":
        NEO4J_CYPHER = os.getenv("NEO4J_PRE_CYPHER", "")
    elif mode == "post":
        NEO4J_CYPHER = os.getenv("NEO4J_POST_CYPHER", "")
    else:
        NEO4J_CYPHER = ""

    if NEO4J_CYPHER == "":
        return

    # prepare cypher statement and quote database name
    cyphers = []
    for cypher in NEO4J_CYPHER.split(";"):
        if (cypher := cypher.strip()) != "":
            cypher = cypher.replace(NEO4J_DATABASE, NEO4J_DATABASE_QUOTED)
            cyphers.append(f"{cypher};")

    # compose the cypher shell command
    cypher_shell = quote_path(os.path.join(NEO4J_BIN, "cypher-shell"))
    for cypher in cyphers:
        command = f"{cypher_shell} -d system -u {NEO4J_USERNAME} -p {NEO4J_PASSWORD} '{cypher}'"
        if verbose:
            print(f"run_cypher: {command}", flush=True)
        try:
            ret = subprocess.run(command, capture_output=True, check=True, shell=True)
            if verbose:
                print(ret.stdout.decode(), flush=True)
        except subprocess.CalledProcessError as e:
            print(f"ERROR: run_cypher: {cypher} statement failed.", flush=True)
            print(e.output)
            raise
