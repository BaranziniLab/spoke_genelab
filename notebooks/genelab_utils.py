import os
import shutil
import glob

from io import StringIO
import json
import hashlib
from urllib.parse import quote
import re
import time
from datetime import datetime
from dateutil.parser import parse
import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv

API_ROOT = "https://visualization.osdr.nasa.gov/biodata/api/v2/"
DATASET_URL = f"{API_ROOT}dataset/"
DATASET_PATH = "../data"  # data download directory
PRIMARY_FACTORS = [
    "Space Flight",
    "Ground Control",
    "Basal Control",
    "Vivarium Control",
]


def setup_environment():
    load_dotenv("../.env", override=True)

    NEO4J_DATA = os.getenv("NEO4J_DATA")
    if not NEO4J_DATA:
        raise Exception("NEO4J_DATA is not set in the .env file!")

    node_dir = os.path.join(NEO4J_DATA, "nodes")
    rel_dir = os.path.join(NEO4J_DATA, "relationships")

    # Create KG directories
    os.makedirs(node_dir, exist_ok=True)
    os.makedirs(rel_dir, exist_ok=True)
    os.makedirs("../data", exist_ok=True)

    print(f"Environment setup for KG version: {os.getenv('KG_VERSION')}")

    return node_dir, rel_dir


def validate_kg_metadata():
    NEO4J_METADATA = os.getenv("NEO4J_METADATA")
    if not NEO4J_METADATA:
        raise Exception("NEO4J_METADATA is not set in the .env file!")

    node_dir = os.path.join(NEO4J_METADATA, "nodes")
    rel_dir = os.path.join(NEO4J_METADATA, "relationships")
    dirs = [node_dir, rel_dir]

    # The following columns are required for a metadata file in that order
    required = ["property", "type", "description", "example"]
    required_cols = ",".join(required)

    error = False
    for d in dirs:
        for fn in glob.glob(os.path.join(d, "*.csv")):
            try:
                cols = pd.read_csv(fn).columns.tolist()
            except Exception as e:
                print(f"Warning: could not parse {fn!r}: {e}")
                continue

            actual_cols = ",".join(cols)
            if required_cols != actual_cols:
                print(
                    f"ERROR: The columns in {fn!r}: {actual_cols} don't match the required columns: {required_cols}"
                )
                error = True

            # TODO
            # Check types
            # Check that the description and example are not empty
            # Check filename syntax
            # Check if node names match the names in the relationship files

    if error:
        raise Exception("ERROR: Invalid metadata files!")

    print("Metadata files passed the check!")


def get_processed_datasets():
    metadata = get_info()
    metadata = filter_by_gl_processed(metadata)
    metadata = metadata.drop_duplicates()
    metadata.fillna("", inplace=True)
    return metadata


def get_info():
    url = (
        f"{API_ROOT}/query/metadata/"
        "?"
        "study.characteristics.organism.term accession number"
        "&"
        "investigation.study assays.study assay technology type"
        "&"
        "investigation.study assays.study assay measurement type"
        "&"
        "study.characteristics.material type"
        "&"
        "study.characteristics.material type.term accession number"
        "&"
        "study.characteristics.host organism"
        "&"
        "study.characteristics.host strain"
        "&"
        "file.category"
        "&"
        "file.subcategory"
        "&"
        "file.file name"
        "&"
        "file.remote_url"
        # Note: the new API formats the header as a single line, but if you needed to break it up like before,
        # we have support for backwards compatibility:
        # "&" "format.header.multi" # you'd use this to break up the header into two lines for the "legacy" format
        # "&" "format.header.mark" # you'd use this to prepend "#" to header lines for the "legacy" format
    )

    metadata = (
        pd.read_csv(quote(url, safe=":/=?&"), na_filter=False)
        .replace(["NaN", "nan", "NA", "NULL", "None"], "")
        .fillna("")
    )

    # Simplify column names
    metadata.rename(
        columns={
            "id.accession": "identifier",
            "investigation.study assays.study assay measurement type": "measurement",
            "investigation.study assays.study assay technology type": "technology",
            "id.assay name": "assay_name",
            "study.characteristics.material type": "material",
            "study.characteristics.host organism": "host_organism",
            "study.characteristics.host strain": "host_strain",
            "file.file name": "filename",
            "file.remote_url": "url",
        },
        inplace=True,
    )

    # Keep only differential analysis files
    metadata = metadata[
        metadata["filename"].str.endswith(".csv")
        & metadata["filename"].str.contains("differential")
    ]

    # Add differential analysis method
    metadata["differential_analysis_method"] = metadata["filename"].apply(
        get_differential_analysis_method
    )

    # Assign taxonomy id
    MESH_TO_TAXID = {"D064307": "13613"}  # MeSH "Microbiota" -> NCBI taxon 13613 (OSD-267)

    def _taxid_from_accession(s):
        m = re.search(r"NCBITAXON/(\d+)$", s, flags=re.I)
        if m:
            return m.group(1)
        return MESH_TO_TAXID.get(s.rsplit("/", 1)[-1], "")

    metadata["taxonomy"] = metadata[
        "study.characteristics.organism.term accession number"
    ].apply(_taxid_from_accession)

    # Complete URL
    metadata["url"] = "https://osdr.nasa.gov" + metadata["url"]

    # Sort by identifier
    metadata = metadata.sort_values(
        by="identifier", key=lambda col: col.str.extract(r"-(\d+)$")[0].astype(int)
    ).reset_index(drop=True)

    # Return selected columns
    metadata = metadata[
        [
            "identifier",
            "technology",
            "measurement",
            "assay_name",
            "taxonomy",
            "material",
            "host_organism",
            "host_strain",
            "filename",
            "url",
            "differential_analysis_method",
            "file.category",
            "file.subcategory",
        ]
    ]

    return metadata.drop_duplicates()


def filter_by_gl_processed(metadata):
    metadata["file.category"] = (
        metadata["file.category"]
        .fillna("")
        .apply(
            lambda s: (
                s if re.search(r"^genelab processed", s, flags=re.IGNORECASE) else False
            )
        )
    )
    metadata["file.subcategory"] = (
        metadata["file.subcategory"]
        .fillna("")
        .apply(
            lambda s: (
                s if re.search(r"^processed data", s, flags=re.IGNORECASE) else False
            )
        )
    )

    metadata = metadata.drop_duplicates().rename(  # there may be multiple "Genelab Processed" lines per sample, etc
        columns={
            "file.category": "file.GL-processed",
            "file.subcategory": "file.non-GL-processed",
        }
    )

    metdata = metadata[
        (metadata["file.GL-processed"] != False)
        | (metadata["file.non-GL-processed"] != False)
    ]

    # These columns are not needed anymore
    metadata = metadata.drop(columns=["file.GL-processed", "file.non-GL-processed"])

    return metadata


def filter_by_technology_type(metadata, technology_types):
    return metadata[
        metadata["technology"].str.lower().isin([x.lower() for x in technology_types])
    ].copy()


def filter_by_host_organism(metadata, taxids):
    # Reverse lookup: host_organism -> taxononmy
    inv_taxids = dict(zip(taxids.values(), taxids.keys()))
    metadata = metadata[
        (metadata["host_organism"] == "") | (metadata["host_organism"].isin(inv_taxids))
    ].copy()
    metadata["host_taxonomy"] = metadata["host_organism"].map(inv_taxids).fillna("")
    return metadata


def filter_by_organism(metadata, taxids):
    metadata = metadata[metadata["taxonomy"].isin(taxids)].copy()
    metadata["organism"] = metadata["taxonomy"].map(taxids)
    return metadata


def download_data_files(assays, file_types, filters, reset=False):
    if reset:
        shutil.rmtree(DATASET_PATH)

    os.makedirs(DATASET_PATH, exist_ok=True)

    file_list = []

    assays = select_differential_expression_file(assays)

    for _, row in assays.iterrows():
        identifier = row["identifier"]
        technology = row["technology"]
        filename = row["filename"]
        url = row["url"]

        file_type = file_types.get(technology, None)
        filter_func = filters.get(file_type, None)

        if file_type:
            try:
                success = download_data_file(url, filename, filter_func, DATASET_PATH)
                time.sleep(0.1)
                if not success:
                    continue

                # Save info about the downloaded file
                file_info = row.copy()
                file_list.append(file_info)

            except requests.exceptions.RequestException as e:
                print(f"Error fetching {url}: {str(e)}")

    df = pd.DataFrame(file_list)
    df.drop_duplicates(inplace=True)

    return df


def select_differential_expression_file(df):
    """Select the preferred differential expression file"""

    # Skip the following types of differential expression files
    skip_terms = ("ERCCnorm", "rRNArm", "UPX")
    df = df[~df["filename"].str.contains("|".join(skip_terms))]

    gl_suffix = "differential_expression_GLbulkRNAseq.csv"
    plain_suffix = "differential_expression.csv"

    is_gl = df["filename"].str.endswith(gl_suffix)
    is_plain = df["filename"].str.endswith(plain_suffix)

    # For each identifier, does any GL file exist?
    has_gl = is_gl.groupby(df["identifier"]).transform("any")

    # Drop plain rows only when GL exists for that identifier
    df = df[~(is_plain & has_gl)]

    return df


def get_differential_analysis_method(file_name):
    if "ancombc1" in file_name:
        return "ANCOM-BC"
    if "ancombc2" in file_name:
        return "ANCOM-BC2"
    if "deseq2" in file_name:
        return "DESeq2"
    if "differential_expression" in file_name:
        return "DESeq2"
    if "differential_methylation" in file_name:
        return "methylKit"
    # default for transcription profiling
    return "DESeq2"


def download_data_file(url, filename, filter_func, dataset_path):
    file_path = os.path.join(dataset_path, filename)

    if not os.path.exists(file_path):
        try:
            response = requests.get(url, allow_redirects=True, timeout=10)
            response.raise_for_status()

            print(f"Downloading: {filename}")

            # Load CSV content into DataFrame
            data = pd.read_csv(StringIO(response.text), low_memory=False)

            # Reduce the size of the data file by applying a filter function
            if filter_func is not None:
                filtered_data = filter_func(data)

            if filtered_data.empty:
                print(f"Skipping file: {filename}. No data after filtering.")
                return False

            # Save the filtered DataFrame
            filtered_data.to_csv(file_path, index=False)

        except requests.exceptions.RequestException as e:
            print(f"Failed to download {filename}: {str(e)}")
    else:
        print(f"File already exist: {filename}")

    return True


def add_reversed_contrast_columns(df):
    """
    Add reversed (y)v(x) columns for columns named like something_(x)v(y).
    For meth.diff_ columns, the values are sign-flipped.
    """
    new_cols = {}

    pattern = re.compile(r"^(?P<prefix>.+)_\((?P<x>.+)\)v\((?P<y>.+)\)$")

    for col in df.columns:
        match = pattern.match(col)
        if not match:
            continue

        prefix = match.group("prefix")
        x = match.group("x")
        y = match.group("y")

        reversed_col = f"{prefix}_({y})v({x})"

        if prefix.startswith("meth.diff"):
            new_cols[reversed_col] = -df[col]
        else:
            new_cols[reversed_col] = df[col]

    return df.assign(**new_cols)


def get_metadata(manifest):
    study_list = []
    for _, row in manifest.iterrows():
        identifier = row["identifier"]
        taxonomy = row["taxonomy"]
        organism = row["organism"]
        host_organism = row["host_organism"]
        host_taxonomy = row["host_taxonomy"]
        host_strain = row["host_strain"]
        study_list.extend(
            extract_metadata(
                identifier,
                taxonomy,
                organism,
                host_organism,
                host_taxonomy,
                host_strain,
            )
        )
        time.sleep(0.1)

    metadata = pd.DataFrame(study_list)
    metadata["host_taxonomy"] = pd.to_numeric(
        metadata["host_taxonomy"], errors="coerce"
    ).apply(lambda x: str(int(x)) if pd.notna(x) else "")

    return metadata


def to_iso_date(date_str) -> str:
    """
    Parse a date string in almost any common format
    and return an ISO‐formatted date "YYYY-MM-DD".
    Returns None if parsing fails.
    """
    try:
        dt = parse(date_str, fuzzy=True)
        return dt.date().isoformat()
    except (ValueError, TypeError):
        return ""


def to_list(x):
    """Always return a list.
    - If x is already a list, return it.
    - If x is None, return [].
    - Otherwise, wrap x in [x].
    """
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def extract_metadata(
    accession, taxonomy, organism, host_organism, host_taxonomy, host_strain
):
    """
    Fetches the JSON for the given OSDR dataset accession (e.g. "OSD-47")
    and extracts:
      - mission_name
      - mission_start_date
      - mission_end_date
      - flight_program
      - space_program
      - project_type
      - project_title
      - description

    Returns a dict with those keys (values will be None if the field is missing).
    """
    url = f"https://visualization.osdr.nasa.gov/biodata/api/v2/dataset/{accession}/?format=json"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    data = response.json()

    # Top-level object for this accession
    ds = data.get(accession, {})

    # Metadata block
    meta = ds.get("metadata", {})
    # print(f"----- {accession} -----")
    # print(json.dumps(meta, indent=2))

    # Progam info
    flight_program = meta.get("flight program", "")
    space_program = meta.get("space program", "")
    project_type = meta.get("project type", "")
    project_title = meta.get("project title", "")
    # Join project titles if there are multiple
    project_title = ", ".join(to_list(project_title))
    description = meta.get("study description", "")

    # Mission info
    mission = meta.get("mission", {})
    raw_name = mission.get("name", "")
    raw_start_date = mission.get("start date", "")
    raw_end_date = mission.get("end date", "")

    # One study may map to multiple missions
    mission_name = to_list(raw_name)
    mission_start_date = to_list(raw_start_date)
    mission_end_date = to_list(raw_end_date)

    study_list = []
    for name, start_date, end_date in zip(
        mission_name, mission_start_date, mission_end_date
    ):
        study = {
            "identifier": accession,
            "project_type": project_type,
            "project_title": project_title,
            "description": description,
            "taxonomy": taxonomy,
            "organism": organism,
            "host_organism": host_organism,
            "host_taxonomy": host_taxonomy,
            "host_strain": host_strain,
            "flight_program": flight_program,
            "space_program": space_program,
            "mission_id": name.replace(" ", "-"),
            "name": name,
            "start_date": to_iso_date(start_date),
            "end_date": to_iso_date(end_date),
        }
        study_list.append(study)

    return study_list


def extract_gene_info(manifest):
    gene_list = []
    for _, row in manifest.iterrows():
        file_path = os.path.join(DATASET_PATH, row["filename"])
        if os.path.exists(file_path):
            # Try if file contains gene data
            try:
                df = pd.read_csv(
                    file_path,
                    usecols=["ENTREZID", "SYMBOL", "GENENAME"],
                    dtype=str,
                    keep_default_na=False,
                )
                df["organism"] = row["organism"]
                df["taxonomy"] = str(row["taxonomy"])
                gene_list.append(df)

            except Exception as e:
                continue

    mgenes = pd.concat(gene_list, ignore_index=True)
    mgenes.drop_duplicates(subset="ENTREZID", inplace=True)

    # Match names of properties in metagraph
    mgenes = mgenes[["ENTREZID", "SYMBOL", "GENENAME", "organism", "taxonomy"]]
    mgenes.rename(
        columns={"ENTREZID": "identifier", "SYMBOL": "symbol", "GENENAME": "name"},
        inplace=True,
    )

    # Remove version number
    mgenes["identifier"] = mgenes.identifier.apply(lambda x: x.split(".")[0])

    return mgenes


def extract_space_factor(factors_list):
    """
    Given a list of factors, return the first one
    that is in PRIMARY_FACTORS, or "" if no match.
    """
    for f in factors_list:
        if f in PRIMARY_FACTORS:
            return f
    return ""


def split_factors(factors_string):
    f1, f2 = factors_string.split(")v(")
    f1 = f1 + ")"
    f2 = "(" + f2
    return f1, f2


def extract_assay_info(manifest, variables):
    manifest["factors"] = manifest.apply(
        get_factor_data,
        args=(DATASET_PATH, variables),
        axis=1,
    )
    # Put each pair of factors into a separate row and split it into 3 columns
    assays = manifest.explode("factors")
    assays["factors"], assays["factors_1"], assays["factors_2"] = zip(
        *assays["factors"]
    )

    # Extract the factor_space that distinguishes space flight from other ground conditions
    assays["factor_space_1"] = assays["factors_1"].apply(extract_space_factor)
    assays["factor_space_2"] = assays["factors_2"].apply(extract_space_factor)

    return assays


def get_factor_data(row, dataset_path, variables):
    file_path = os.path.join(dataset_path, row["filename"])
    data = pd.read_csv(file_path, low_memory=False, nrows=1)
    cols = data.columns
    end_points = variables.get(row["differential_analysis_method"], "")
    if end_points == "":
        print(
            f"Error: no relevant columns found in file {row['filename']} for {variables.keys()} differential analysis methods"
        )
        return []
    factors = [get_factors(col) for col in cols if col.startswith(end_points)]

    return factors


def get_factors(column_name):
    factors_string = column_name.split("_", 1)[1]
    parts = column_name.split(")v(")
    part1 = parts[0].split("(")[1]
    part2 = parts[1]
    factors_1 = [x.strip(" ()") for x in part1.split("&")]
    factors_2 = [x.strip(" ()") for x in part2.split("&")]

    return factors_string, factors_1, factors_2


def extract_materials(assays):
    # Extract cell or tissue types from the factors lists and materials column
    factors_1 = assays["factors_1"].to_list()
    unique_factors_1 = [item for sublist in factors_1 for item in sublist]
    factors_2 = assays["factors_2"].to_list()
    unique_factors_2 = [item for sublist in factors_2 for item in sublist]
    materials = assays["material"].to_list()

    unique_factors = sorted(set(unique_factors_1 + unique_factors_2 + materials))
    materials = pd.DataFrame(unique_factors, columns=["material"])
    return materials


def assign_material_to_assays(assays, mapped_materials):
    material_dict = {
        row["material"]: (row["material"], row["material_name"], row["material_id"])
        for _, row in mapped_materials.iterrows()
    }
    assays[
        [
            "material_1",
            "material_2",
            "material_name_1",
            "material_name_2",
            "material_id_1",
            "material_id_2",
        ]
    ] = assays.apply(assign_material, material_dict=material_dict, axis=1)
    return assays


def assign_material(row, material_dict):
    # Assign material to each factor. If a factor doesn't contain a material,
    # use the default material specified for the assay
    default = material_dict.get(row["material"], (row["material"], "", ""))
    mat1 = next((m for f in row["factors_1"] if (m := material_dict.get(f))), default)
    mat2 = next((m for f in row["factors_2"] if (m := material_dict.get(f))), default)
    return pd.Series([mat1[0], mat2[0], mat1[1], mat2[1], mat1[2], mat2[2]])


def add_assay_identifiers(assays):
    # pre‑compute each row’s MD5 hash of its JSON representation
    hashes = [
        hashlib.md5(json.dumps(r, sort_keys=True).encode()).hexdigest()
        for r in assays.to_dict("records")
    ]
    return assays.assign(
        study_id=assays["identifier"],
        assay_hash=hashes,
        identifier=lambda df: df["study_id"].str.cat(df["assay_hash"], sep="-"),
    )


def extract_transcription_data(assays: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """
    For each transcription‑profiling assay in `assays`, read its file once,
    extract ENTREZID/log2fc/adj_p.value columns, filter by threshold, and
    return a DataFrame of edges with columns ['from', 'to', 'log2fc', 'adj_p_value',
    'group_mean_1', 'group_stdev_1', 'group_mean_2', 'group_stdev_2'].
    """
    print("extract_transcription_data:", threshold)
    rows = []
    cols = [
        "from",
        "to",
        "log2fc",
        "adj_p_value",
        "group_mean_1",
        "group_stdev_1",
        "group_mean_2",
        "group_stdev_2",
    ]

    # Filter to transcription profiling and group by filename
    tp = assays[assays["measurement"] == "transcription profiling"]
    for filename, grp in tp.groupby("filename"):
        # Print study_id when loading a new file
        print(f"processing: {grp['study_id'].iat[0]}")
        df = pd.read_csv(os.path.join(DATASET_PATH, filename), low_memory=False)

        for _, row in grp.iterrows():
            f = row["factors"]
            f1, f2 = split_factors(f)
            log2fc_col = f"Log2fc_{f}"
            adj_col = f"Adj.p.value_{f}"
            group_mean_col1 = f"Group.Mean_{f1}"
            group_stdev_col1 = f"Group.Stdev_{f1}"
            group_mean_col2 = f"Group.Mean_{f2}"
            group_stdev_col2 = f"Group.Stdev_{f2}"

            # Skip if expected columns are missing
            if not {
                log2fc_col,
                adj_col,
                group_mean_col1,
                group_stdev_col1,
                group_mean_col2,
                group_stdev_col2,
            }.issubset(df.columns):
                continue

            # Select columns
            sub = df[
                [
                    "ENTREZID",
                    log2fc_col,
                    adj_col,
                    group_mean_col1,
                    group_stdev_col1,
                    group_mean_col2,
                    group_stdev_col2,
                ]
            ]

            # Require the following data to be present
            sub = sub.dropna(subset=["ENTREZID", log2fc_col, adj_col])

            # Filter by p‑value threshold
            sub = sub[sub[adj_col] <= threshold]
            if sub.empty:
                print(
                    f"No statistically significant data for {row.study_id}: {log2fc_col}"
                )
                continue

            # Rename to Neo4j convention
            sub = sub.rename(
                columns={
                    "ENTREZID": "to",
                    log2fc_col: "log2fc",
                    adj_col: "adj_p_value",
                    group_mean_col1: "group_mean_1",
                    group_stdev_col1: "group_stdev_1",
                    group_mean_col2: "group_mean_2",
                    group_stdev_col2: "group_stdev_2",
                }
            )
            sub["from"] = row["identifier"]  # direct assignment of "from"
            sub["to"] = sub["to"].astype(int)

            # Keep only the four columns in order
            sub = sub[cols]
            rows.append(sub)

    # Concatenate or return empty
    if rows:
        return pd.concat(rows, ignore_index=True).fillna("")
    return pd.DataFrame(columns=cols)


def extract_methylation_data(
    assays: pd.DataFrame, threshold: float = 0.05
) -> pd.DataFrame:
    """
    For each DNA‑methylation‑profiling assay in `assays`, read its file once,
    extract ENTREZID/methylation_diff/q_value and region columns, filter by
    q‑value threshold, and return a DataFrame with the combined results.
    """
    print("extract_methylation_data:", threshold)
    rows = []
    cols = [
        "ENTREZID",
        "methylation_diff",
        "q_value",
        "group_mean_1",
        "group_stdev_1",
        "group_mean_2",
        "group_stdev_2",
        "chr",
        "start",
        "end",
        "dist.to.feature",
        "in_promoter",
        "in_exon",
        "in_intron",
        "assay_id",
        "methylation_id",
    ]

    # Filter by DNA methylation profiling and group by file
    dm = assays[assays["measurement"] == "DNA methylation profiling"]
    for filename, grp in dm.groupby("filename"):
        # print study_id when loading each file
        print(f"processing: {grp['study_id'].iat[0]}")
        df = pd.read_csv(os.path.join(DATASET_PATH, filename), low_memory=False)

        for _, row in grp.iterrows():
            f = row["factors"]
            f1, f2 = split_factors(f)
            diff_col = f"meth.diff_{f}"
            qv_col = f"qvalue_{f}"
            group_mean_col1 = f"Group.Mean_{f1}"
            group_stdev_col1 = f"Group.Stdev_{f1}"
            group_mean_col2 = f"Group.Mean_{f2}"
            group_stdev_col2 = f"Group.Stdev_{f2}"

            # skip if expected columns are missing
            if not {
                diff_col,
                qv_col,
                group_mean_col1,
                group_stdev_col1,
                group_mean_col2,
                group_stdev_col2,
            }.issubset(df.columns):
                continue

            # select columns
            sub = df[
                [
                    "ENTREZID",
                    diff_col,
                    qv_col,
                    group_mean_col1,
                    group_stdev_col1,
                    group_mean_col2,
                    group_stdev_col2,
                    "chr",
                    "start",
                    "end",
                    "dist.to.feature",
                    "prom",
                    "exon",
                    "intron",
                ]
            ]

            # Require the following data to be present
            sub = sub.dropna(
                subset=[
                    "ENTREZID",
                    diff_col,
                    qv_col,
                    "chr",
                    "start",
                    "end",
                    "dist.to.feature",
                    "prom",
                    "exon",
                    "intron",
                ]
            )

            # filter by q‑value threshold
            sub = sub[sub[qv_col] <= threshold]
            if sub.empty:
                print(f"No significant data for {row['study_id']}: {diff_col}")
                continue

            # rename to standard column names
            sub = sub.rename(
                columns={
                    diff_col: "methylation_diff",
                    qv_col: "q_value",
                    group_mean_col1: "group_mean_1",
                    group_stdev_col1: "group_stdev_1",
                    group_mean_col2: "group_mean_2",
                    group_stdev_col2: "group_stdev_2",
                    "prom": "in_promoter",
                    "exon": "in_exon",
                    "intron": "in_intron",
                }
            )

            # map 0/1 → 'false'/'true'
            neo4j_bool = {1: "true", 0: "false"}
            sub["in_promoter"] = sub["in_promoter"].map(neo4j_bool)
            sub["in_exon"] = sub["in_exon"].map(neo4j_bool)
            sub["in_intron"] = sub["in_intron"].map(neo4j_bool)

            # add assay_id and methylation_id
            sub["assay_id"] = row["identifier"]
            sub["methylation_id"] = (
                sub["chr"]
                + ":"
                + sub["start"].astype(str)
                + "-"
                + sub["end"].astype(str)
            )

            # keep columns in the desired order
            rows.append(sub[cols])

    # concatenate or return empty frame with proper columns
    if rows:
        return pd.concat(rows, ignore_index=True).fillna("")
    return pd.DataFrame(columns=cols)


def extract_amplicon_deseq2_data(
    assays: pd.DataFrame, threshold: float
) -> pd.DataFrame:
    """
    For each amplicon sequencing assay in `assays`, read its file once,
    extract NCBI_id, best_taxonomy, Log2fc, and Adj.p.value columns, filter by threshold, and
    return a DataFrame of edges with columns ["from", "to", "name", "log2fc", "adj_p_value", "group_mean_1", "group_stdev_1", "group_mean_2", "group_stdev_2"].
    """
    print("extract_amplicon_data:", threshold)
    rows = []
    cols = [
        "from",
        "to",
        "name",
        "log2fc",
        "adj_p_value",
        "group_mean_1",
        "group_stdev_1",
        "group_mean_2",
        "group_stdev_2",
    ]

    # Filter DESeq2 data and group by filename
    tp = assays[
        (assays["measurement"] == "Amplicon Sequencing")
        & (assays["differential_analysis_method"] == "DESeq2")
    ]
    for filename, grp in tp.groupby("filename"):
        # Print study_id when loading a new file
        print(f"processing: {grp['study_id'].iat[0]}")
        df = pd.read_csv(os.path.join(DATASET_PATH, filename), low_memory=False)

        for _, row in grp.iterrows():
            f = row["factors"]
            f1, f2 = split_factors(f)
            log2fc_col = f"Log2fc_{f}"
            adj_col = f"Adj.p.value_{f}"
            group_mean_col1 = f"Group.Mean_{f1}"
            group_stdev_col1 = f"Group.Stdev_{f1}"
            group_mean_col2 = f"Group.Mean_{f2}"
            group_stdev_col2 = f"Group.Stdev_{f2}"

            # Skip if expected columns are missing
            if not {log2fc_col, adj_col}.issubset(df.columns):
                continue

            # Select columns
            sub = df[
                [
                    "NCBI_id",
                    "best_taxonomy",
                    log2fc_col,
                    adj_col,
                    group_mean_col1,
                    group_stdev_col1,
                    group_mean_col2,
                    group_stdev_col2,
                ]
            ]

            # Require the following data to be present
            sub = sub.dropna(
                subset=[
                    "NCBI_id",
                    "best_taxonomy",
                    log2fc_col,
                    adj_col,
                ]
            )

            # Filter by p‑value threshold
            sub = sub[sub[adj_col] <= threshold]
            if sub.empty:
                print(
                    f"No statistically significant data for {row.study_id}: {log2fc_col}"
                )
                continue

            # Rename to Neo4j convention
            sub = sub.rename(
                columns={
                    "NCBI_id": "to",
                    "best_taxonomy": "name",
                    log2fc_col: "log2fc",
                    adj_col: "adj_p_value",
                    group_mean_col1: "group_mean_1",
                    group_stdev_col1: "group_stdev_1",
                    group_mean_col2: "group_mean_2",
                    group_stdev_col2: "group_stdev_2",
                }
            )
            sub["from"] = row["identifier"]  # direct assignment of "from"
            sub["to"] = sub["to"].astype(int)

            # Keep only the four columns in order
            sub = sub[cols]
            rows.append(sub)

    # Concatenate or return empty
    if rows:
        return pd.concat(rows, ignore_index=True).fillna("")
    return pd.DataFrame(columns=cols)


def extract_amplicon_ancombc_data(
    assays: pd.DataFrame, threshold: float
) -> pd.DataFrame:
    """
    For each amplicon sequencing assay in `assays`, read its file once,
    extract NCBI_id, best_taxonomy, Lnfc and Q.value columns, filter by threshold, and
    return a DataFrame of edges with columns  ["from", "to", "name", "lnfc", "log2fc", "q_value", "group_mean_1", "group_stdev_1", "group_mean_2", "group_stdev_2"].
    """
    print("extract_amplicon_data:", threshold)
    rows = []
    cols = [
        "from",
        "to",
        "name",
        "lnfc",
        "log2fc",
        "q_value",
        "group_mean_1",
        "group_stdev_1",
        "group_mean_2",
        "group_stdev_2",
    ]

    # Filter ANCOM-BC data and group by filename
    tp = assays[
        (assays["measurement"] == "Amplicon Sequencing")
        & (assays["differential_analysis_method"].isin(["ANCOM-BC", "ANCOM-BC2"]))
    ]
    for filename, grp in tp.groupby("filename"):
        print("ANCOM-BC:", filename)
        # Print study_id when loading a new file
        print(f"processing: {grp['study_id'].iat[0]}")
        df = pd.read_csv(os.path.join(DATASET_PATH, filename), low_memory=False)

        for _, row in grp.iterrows():
            f = row["factors"]
            f1, f2 = split_factors(f)
            lnfc_col = f"Lnfc_{f}"
            qvalue_col = f"Q.value_{f}"
            group_mean_col1 = f"Group.Mean_{f1}"
            group_stdev_col1 = f"Group.Stdev_{f1}"
            group_mean_col2 = f"Group.Mean_{f2}"
            group_stdev_col2 = f"Group.Stdev_{f2}"

            # Skip if expected columns are missing
            if not {lnfc_col, qvalue_col}.issubset(df.columns):
                continue

            # Select columns
            sub = df[
                [
                    "NCBI_id",
                    "best_taxonomy",
                    lnfc_col,
                    qvalue_col,
                    group_mean_col1,
                    group_stdev_col1,
                    group_mean_col2,
                    group_stdev_col2,
                ]
            ]

            # Require the following data to be present
            sub = sub.dropna(
                subset=[
                    "NCBI_id",
                    "best_taxonomy",
                    lnfc_col,
                    qvalue_col,
                ]
            )
            # Filter by q‑value threshold
            sub = sub[sub[qvalue_col] <= threshold]
            if sub.empty:
                print(
                    f"No statistically significant data for {row.study_id}: {lnfc_col}"
                )
                continue

            # Rename to Neo4j convention
            sub = sub.rename(
                columns={
                    "NCBI_id": "to",
                    "best_taxonomy": "name",
                    lnfc_col: "lnfc",
                    qvalue_col: "q_value",
                    group_mean_col1: "group_mean_1",
                    group_stdev_col1: "group_stdev_1",
                    group_mean_col2: "group_mean_2",
                    group_stdev_col2: "group_stdev_2",
                }
            )
            sub["from"] = row["identifier"]  # direct assignment of "from"
            sub["to"] = sub["to"].astype(int)
            # Convert to log2fc so results from different methods are comparable
            sub["log2fc"] = sub["lnfc"] / np.log(2)

            # Keep the columns in order
            sub = sub[cols]
            rows.append(sub)

    # Concatenate or return empty
    if rows:
        #        return pd.concat(rows, ignore_index=True)
        df = pd.concat(rows, ignore_index=True).fillna("")

        return df
    return pd.DataFrame(columns=cols)


def list_to_string(df):
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, list)).all():
            df[col] = df[col].apply(lambda x: "|".join(map(str, x)))

    return df


def save_dataframe_to_kg(df, node_or_rel_name, node_or_rel_directory):
    # Remove previous versions of the node or relationship file
    for file_path in glob.glob(
        os.path.join(node_or_rel_directory, f"{node_or_rel_name}_*.csv")
    ):
        os.remove(file_path)

    # Convert any column of type list to a "|" separated string (required for Neo4j import)
    df = list_to_string(df)

    # Remove duplicate nodes or relationships
    if "identifier" in df.columns and "nodes" in node_or_rel_directory:
        df = df.drop_duplicates(subset="identifier")
    elif {"from", "to"}.issubset(
        df.columns
    ) and "relationships" in node_or_rel_directory:
        df = df.drop_duplicates(subset=["from", "to"])
    else:
        raise ValueError(
            f"Invalid node or relationship file {list(df.columns)} or directory {node_or_rel_directory}. See https://github.com/sbl-sdsc/kg-import for details."
        )

    update_date = datetime.today().strftime("%Y-%m-%d")
    df.to_csv(
        os.path.join(node_or_rel_directory, f"{node_or_rel_name}_{update_date}.csv"),
        index=False,
    )

    return df
