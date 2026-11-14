# Change Log

## v0.3.1+20261112

Compared with the previous release, [v0.3.1+20260311](https://github.com/BaranziniLab/spoke_genelab/tree/v0.3.1+20260311).

The graph schema is unchanged: the node and relationship metadata in `kg/v0.3.1/metadata/` and `kg/v0.3.1/style.grass` are identical to the previous release. This release contains pipeline fixes and a rebuild of the knowledge graph from OSDR on 11/12/2026.

| | v0.3.1+20260311 | v0.3.1+20261112 |
|---|---|---|
| Data retrieved from OSDR | 3/10/2026 | 11/12/2026 |
| Neo4j version used for the build | 2025.12.1 | 2026.10.2 |
| Schema version | v0.3.1 | v0.3.1 |
| Default database name | `spoke-genelab-v0.3.1` | `spoke-genelab-v0.3.1-20261112` |

---

## 1. Updates to files in the GitHub repository

### Pipeline code

- **`notebooks/genelab_utils.py`**
  - Taxonomy assignment in `get_info()` now recognises the MeSH term "Microbiota" (`D064307`) and maps it to NCBI taxon 13613, so that OSD-267 keeps its organism after its OSDR annotation changed from an NCBI Taxonomy term to a MeSH term. NCBI Taxonomy accessions are now parsed with a regular expression instead of a fixed URL prefix. (PR #10)
  - Fixed a misspelled variable (`metdata`) in `filter_by_gl_processed()` that prevented the filter for processed data files from being applied. The correction does not change the content of this release: the only files it excludes (GLDS-586 and GLDS-587) contain no data that passes the significance filters.
- **`notebooks/ortholog_mapper.py`** — The HCOP ortholog file is now downloaded from HGNC's new location on Google Cloud Storage (`storage.googleapis.com/public-download-files/hcop/`); the previous `ftp.ebi.ac.uk` URL no longer works. (Issue #8, PR #9)
- **`notebooks/neo4j_bulk_importer.py`**
  - `DROP DATABASE … IF EXISTS` and `CREATE OR REPLACE DATABASE` now end with `WAIT`, so the bulk import no longer starts before the database has been dropped or created. (Issue #11, PR #12)
  - The `NEO4J_ADMIN_JAVA_OPTS` heap setting, which `neo4j-admin` ignored, was removed from the import command. (Issue #13, PR #14)
  - Fixed `dump_database()`, which referenced an undefined variable (`version`) and a misspelled variable (`eo4j_dump`). The dump directory is now named after the `KG_VERSION` environment variable.
- **`notebooks/PrepareNeo4jBulkImport.ipynb`**
  - The node uniqueness constraint is now created on `n.identifier` instead of `n.id`, which does not exist in this graph. (Issue #15, PR #17)
  - All file names written to `args.txt` are now prefixed with `./`. Neo4j 2026.10.2 rejects bare file names with "Unable to find the parent of the path".

### Configuration and documentation

- **`env_template`**
  - Removed the unused `NEO4J_ADMIN_JAVA_OPTS` variable.
  - Added a `DATE` variable (`YYYYMMDD`). The database name now includes the build date: `NEO4J_DATABASE=spoke-genelab-${KG_VERSION}-${DATE}`, for example `spoke-genelab-v0.3.1-20261112`.
- **`environment.yml`**
  - OpenJDK updated from 23.0.2 to 25.0.2. Neo4j 2025.10 and later support Java 21 and Java 25.
  - The `anaconda` channel was replaced with `bioconda`.
- **`docs/create_kg.md`**
  - Rewritten for Neo4j Desktop 2.x: the steps use the current terminology (instance, `Connect` > `Query`, `Export database to .dump`) and the Neo4j Desktop 2.x screenshots, and the example `NEO4J_INSTALL_PATH` uses the current folder layout.
  - Added a prerequisites section, including the minimum Neo4j version (2026.09) required by the full-text search examples in notebook 5.
  - Added the `DATE` variable to the `.env` instructions and updated the database and dump file names to the dated form (`spoke-genelab-v0.3.1-20261112`).
  - Removed the instructions for `NEO4J_ADMIN_JAVA_OPTS`.
- **`docs/import_db.md`** — The download link now points to the new dump file (`spoke-genelab-v0.3.1-20261112.dump`), its MD5 checksum was added, and the database name to enter was updated to `spoke-genelab-v0.3.1-20261112`.
- **`README.md`** — The MCP-GeneLab configuration example now uses the database name `spoke-genelab-v0.3.1-20261112`. A link to the change log was added.
- **`CHANGELOG.md`** — Added.
- **`docs/methylation_gene_expression.png`** — Regenerated from the corrected query in notebook 6. It now shows the two OSD-48 genes that are hypermethylated in the promoter and downregulated (*Igfbp6* and *Pcdh19*).

### Notebooks

- **`notebooks/4_create_assay_nodes.ipynb`** — Material mapping now keeps only UBERON and Cell Ontology identifiers. Factor values that the ontology service maps to other ontologies (for example "CO2" and "proton" to ChEBI terms) are no longer treated as tissues or cell types.
- **`notebooks/5_import_to_neo4j.ipynb`** — The two full-text search examples now use the Cypher 25 `SEARCH` clause instead of `db.index.fulltext.queryNodes`, and return the relevance score. This requires Neo4j 2026.09 or later. (Issue #16, PR #18)
- **`notebooks/6_query_examples.ipynb`**
  - *Gene Methylation vs Downregulation*: the expression condition was corrected from `m2.log2fc > $log2fc_threshold` to `m2.log2fc < $log2fc_threshold`. The previous condition returned genes that were not downregulated.
  - *Comparison of Gene Methylation vs. Gene Expression*: the description now states the correct direction (Space Flight vs. Ground Control). The query now keeps only contrasts in which all factors other than spaceflight match (for example Carcass vs. Carcass), returns the gene symbol, and no longer returns duplicate factor columns.
- **Notebooks 1–6** — All saved outputs are from the 11/12/2026 build.

### Unchanged

`docs/neo4j_installation.md`, `kg/v0.3.1/` (metadata and style sheet), `notebooks/neo4j_utils.py`, `notebooks/ontology_mapper.py`, `notebooks/utils.py`.

---

## 2. Changes in the SPOKE-GeneLab knowledge graph

### Node counts

| Node | v0.3.1+20260311 | v0.3.1+20261112 | Change |
|---|---:|---:|---:|
| MGene | 138,736 | 124,549 | −14,187 |
| Gene | 30,009 | 30,170 | +161 |
| Assay | 13,146 | 13,614 | +468 |
| MethylationRegion | 8,003 | 8,003 | 0 |
| Study | 212 | 222 | +10 |
| Organism | 46 | 46 | 0 |
| Anatomy | 42 | 45 | +3 |
| Mission | 42 | 42 | 0 |
| CellType | 7 | 6 | −1 |
| **Total** (excluding 9 MetaNodes) | **190,243** | **176,697** | **−13,546** |

### Relationship counts

| Relationship | v0.3.1+20260311 | v0.3.1+20261112 | Change |
|---|---:|---:|---:|
| Assay–MEASURED_DIFFERENTIAL_EXPRESSION_ASmMG→MGene | 50,208,066 | 50,836,284 | +628,218 |
| MGene–IS_ORTHOLOG_MGiG→Gene | 121,153 | 102,699 | −18,454 |
| Assay–MEASURED_DIFFERENTIAL_METHYLATION_ASmMR→MethylationRegion | 27,454 | 27,454 | 0 |
| Study–PERFORMED_SpAS→Assay | 13,146 | 13,614 | +468 |
| MGene–METHYLATED_IN_MGmMR→MethylationRegion | 8,270 | 8,270 | 0 |
| Assay–INVESTIGATED_ASiA→Anatomy | 7,214 | 7,690 | +476 |
| Assay–INVESTIGATED_ASiCT→CellType | 1,240 | 1,174 | −66 |
| Assay–MEASURED_DIFFERENTIAL_ABUNDANCE_ASmO→Organism | 193 | 193 | 0 |
| Mission–CONDUCTED_MIcS→Study | 127 | 132 | +5 |
| **Total** (excluding 9 MetaRelationships) | **50,386,863** | **50,997,510** | **+610,647** |

DNA methylation and amplicon (differential abundance) content is unchanged. All changes are in transcription profiling data.

### Studies added (16)

| Study | GeneLab ID | Organism | Project type | Project / mission | Material |
|---|---|---|---|---|---|
| OSD-138 | GLDS-138 | *Bacillus subtilis* | Spaceflight | BRIC-23 / SpaceX-9 | Cells |
| OSD-185 | GLDS-185 | *Bacillus subtilis* | Spaceflight | BRIC-21 / SpaceX-6 | Cells |
| OSD-274 | GLDS-274 | *Mus musculus* | Ground | Rapid Freeze hardware preservation | Soleus |
| OSD-720 | GLDS-699 | *Mus musculus* | Ground | Gamma and simulated GCR irradiation | Left ventricle |
| OSD-811 | GLDS-693 | *Homo sapiens* | Spaceflight | MVP2-Cell-03 / SpaceX-20 | Cultured cells |
| OSD-813 | GLDS-695 | *Mus musculus* | Ground | Low dose rate neutron irradiation | Placenta |
| OSD-825 | GLDS-701 | *Mus musculus* | Ground | Western diet | Left ventricle |
| OSD-876 | GLDS-722 | *Mus musculus* | Ground | Hindlimb unloading | Gastrocnemius |
| OSD-880 | GLDS-724 | *Mus musculus* | Ground | Hindlimb unloading | Gastrocnemius |
| OSD-899 | GLDS-728 | *Mus musculus* | Spaceflight | RR-10 / SpaceX-21 | Cecum |
| OSD-900 | GLDS-729 | *Mus musculus* | Spaceflight | RR-10 / SpaceX-21 | Right lung |
| OSD-901 | GLDS-730 | *Mus musculus* | Spaceflight | MELFI / SpaceX-25, SpaceX-26 | Cultured cells |
| OSD-935 | GLDS-763 | *Mus musculus* | Ground | Hindlimb unloading and X-ray irradiation | Soleus |
| OSD-949 | GLDS-774 | *Mus musculus* | Ground | Hindlimb unloading | Soleus |
| OSD-955 | GLDS-778 | *Mus musculus* | Ground | Mitochondrial translation (mouse) | Soleus |
| OSD-993 | GLDS-805 | *Homo sapiens* | Ground | Space radiation (gamma, proton, heavy ion) | Cultured cells |

All 16 are RNA-Seq transcription profiling studies. OSD-138 was evaluated for the previous release but had no rows that passed the filters.

### Studies removed (6)

These studies were in the previous release and are no longer available from OSDR. Together they accounted for 94 assays and 241,244 differential expression relationships.

| Study | Organism | Project type | Technology | Assays removed | Status in OSDR (11/12/2026) |
|---|---|---|---|---:|---|
| OSD-213 | *Arabidopsis thaliana* | Spaceflight (Shenzhou 8) | DNA microarray | 6 | Study no longer listed |
| OSD-308 | *Mus musculus* | Ground | RNA-Seq | 2 | Study no longer listed |
| OSD-373 | *Danio rerio* | Ground | RNA-Seq | 12 | Study no longer listed |
| OSD-469 | *Arabidopsis thaliana* | Spaceflight (SJ-10) | DNA microarray | 56 | Study no longer listed |
| OSD-547 | *Mus musculus* | Ground | DNA microarray | 12 | Study no longer listed |
| OSD-903 | *Homo sapiens* | Spaceflight (AX-1) | RNA-Seq | 6 | Study listed, processed data files withdrawn |

### Studies with updated differential expression data (40)

- **Reprocessed (39 studies):** OSDR replaced the older `GLDS-###_rna_seq_differential_expression.csv` file with a file from the current GeneLab bulk RNA-Seq pipeline (`…_GLbulkRNAseq.csv`). Differential expression relationships and assay identifiers for these studies may differ from the previous release.
  - *Mus musculus* (25), *Arabidopsis thaliana* (10), *Homo sapiens* (3), *Drosophila melanogaster* (1)
  - OSD-38, 100, 137, 162, 168, 194, 201, 211, 214, 218, 235, 237, 238, 240, 241, 242, 251, 254, 255, 270, 272, 273, 294, 295, 321, 323, 347, 352, 397, 406, 426, 476, 498, 502, 508, 510, 511, 539, 540
- **OSD-936:** the flight differential expression file (`GLDS-764_…_FLT_GLbulkRNAseq.csv`) is now included in addition to the ground file.

### Organisms

- **Removed: *Danio rerio* (taxon 7955).** OSD-373 was the only zebrafish study. The previous release contained 17,142 zebrafish MGene nodes and 18,646 zebrafish ortholog relationships, which accounts for most of the decrease in MGene nodes and IS_ORTHOLOG relationships.
- **Added: *Bacillus subtilis* (taxon 1423).** Introduced by OSD-138 and OSD-185. No human orthologs are available for this organism, so it has no IS_ORTHOLOG relationships.

### Anatomy and cell type (proxy nodes)

- **Anatomy added:** cecum (UBERON:0001153), placenta (UBERON:0001987), left ventricle (UBERON:0002084), right lung (UBERON:0002167).
- **Anatomy removed:** embryo (UBERON:0000922), with the removal of OSD-373.
- **CellType removed:** zygote (CL:0010017), with the removal of OSD-308.
- **Identifier changes:** the BioPortal mapping returned a different UBERON identifier for two existing terms. Assays that used these terms now link to the new identifier.
  - skin: UBERON:0001003 → UBERON:0002199 (materials "dorsal skin", "femoral skin", "femoral lateral skin")
  - hippocampus: UBERON:0002961 → UBERON:0002421 (material "Right hippocampus")
