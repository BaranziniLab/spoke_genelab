## ⚙️ Create spoke-genelab Knowledge Graph 

### Prerequisites

* Neo4j Desktop 2.x with a `spoke-genelab` instance and the APOC plugin, set up as described in [Neo4j Desktop Installation and Configuration](neo4j_installation.md).
* Neo4j version 2026.09 or later for the instance. The full-text search examples in `5_import_to_neo4j.ipynb` use the Cypher 25 `SEARCH` clause, which is not available in earlier versions. The current release was built with Neo4j 2026.10.2.
* Miniconda3 (light-weight, preferred) or Anaconda3 and Mamba (faster than Conda)

    * Install [Miniconda3](https://docs.conda.io/en/latest/miniconda.html)
    * Update an existing miniconda3 installation: ```conda update conda```
    * Install Mamba: ```conda install mamba -n base -c conda-forge```
    * Install Git (if not installed): ```conda install git -n base -c anaconda```

------

### Setup the Environment

1. Clone this Repository

```
git clone https://github.com/BaranziniLab/spoke_genelab.git
cd spoke_genelab
```

2. Create a Conda environment

The file `environment.yml` specifies the Python version and all required dependencies.

```
mamba env create -f environment.yml
```

3. Create an account in [BioPortal](https://bioportal.bioontology.org/) and copy the API key. BioPortal is used to map terms to ontologies.

   
4. Copy the file `env_template` to `.env`

5. Edit the file `.env` and set the following variables

KG version number

`KG_VERSION=v0.3.1`

Build date in the format `YYYYMMDD`. The date is appended to the database name, e.g., `spoke-genelab-v0.3.1-20261112`.

`DATE=20261112`

Path to the cloned git repository

`KG_GIT=/Users/.../spoke_genelab/`

Path to the Neo4j instance in Neo4j Desktop. The path is shown in the `Path` field of the `spoke-genelab` instance in Neo4j Desktop. Make sure to enclose the path in quotes.

`NEO4J_INSTALL_PATH="/Users/.../Library/Application Support/neo4j-desktop/Application/Data/dbmss/dbms-<instance ID>"`

BioPortal API Key

`BIOPORTAL_API_KEY=<bioportal api key>`

------

### Download and Process Datasets and upload to Neo4J Graph Database

1. Launch Neo4j Desktop and start the `spoke-genelab` instance

<p align="center">
  <img src="start_instance.png" width="600">
</p>

----
2. Activate the conda environment

```
conda activate spoke-genelab
```

3. Launch Jupyter Lab

```
jupyter lab
```

4. Navigate to the `notebooks` directory and run the following notebooks


| Notebook                   |   Description           |
|----------------------------|-------------------------|
| 1_download_datasets.ipynb  | Downloads datasets     |
| 2_create_study_mission_nodes.ipynb | Creates Study and Mission nodes and their relationships |
| 3_create_gene_nodes.ipynb  | Creates MGene (model organism) and mapped Gene (human) gene nodes |
| 4_create_assay_nodes.ipynb | Creates Assay nodes and their relationships |
| 5_import_to_neo4j.ipynb    | Imports the formatted data into a Neo4j KG |
| 6_query_examples.ipynb     | Runs example queries (optional) |

5. When the import is completed, click the refresh icon above the list of databases in Neo4j Desktop. The newly created database, e.g., `spoke-genelab-v0.3.1-20261112`, will be listed.

6. Select `Query` from the `Connect` menu

<p align="center">
  <img src="select_query.png" width="600">
</p>

7. Select the newly created database, e.g., `spoke-genelab-v0.3.1-20261112`. Wait for about 30+ seconds until the database is loaded and the nodes are listed as shown below.

<p align="center">
  <img src="select_db.png" width="600">
</p>

8. Set the Graph Stylesheet

Drag the file kg/v0.3.1/style.grass onto the query window to set the node colors, sizes, and labels.

9. Now you are ready to run Cypher queries on the selected database.

10. When you are finished, stop the instance in Neo4j Desktop.

To stop the conda environment, type

```conda deactivate```

------

### Dump Neo4J Graph Database

1. Stop the instance

> A database can only be exported from a stopped instance.

<p align="center">
  <img src="stop_instance.png" width="600">
</p>

2. Select `Export database to .dump` from the `...` menu next to the database, e.g., `spoke-genelab-v0.3.1-20261112`.

3. When the export is complete, locate the dump file, e.g., `spoke-genelab-v0.3.1-20261112.dump`.

This database dump is used to distribute the KG (see [Import spoke-genelab Knowledge Graph](import_db.md)) and to create the SPOKE-GeneLab composite database.
