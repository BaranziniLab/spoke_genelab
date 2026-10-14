## 📥 Import spoke-genelab Knowledge Graph

> Note: The spoke-genelab instance can hold multiple versions of the spoke-genelab KG.

1. Download the Neo4j dump file

[![Download spoke-genelab-v0.3.1](https://img.shields.io/badge/Download-spoke--genelab--v0.3.1-brightgreen)](https://drive.google.com/file/d/1Wy-BqUhtmGk7qB8WpnG5LefDDsF_6xQW/view?usp=sharing)

2. Launch Neo4j Desktop and start the `spoke-genelab` instance

<p align="center">
  <img src="start_instance.png" width="600">
</p>

3. Click `Create database` 

<p align="center">
  <img src="create_db_menu.png" width="600">
</p>

4. Enter the exact database name, e.g., spoke-genelab-v0.3.1

<p align="center">
  <img src="create_db.png" width="400">
</p>

5. Stop the instance

> A database can only be imported into a stopped instance.

<p align="center">
  <img src="stop_instance.png" width="600">
</p>

6. Select `Load database from file` from the `...` menu next to the new database

<p align="center">
  <img src="load_from_db.png" width="600">
</p> 

7. Import dump file

> Choose the option: `Allow overwriting` when importing the file.

 <p align="center">
  <img src="select_dump_file.png" width="600">
</p>  

## Optional: Explore the KG

8. Start the instance

<p align="center">
  <img src="start_instance.png" width="600">
</p>

9. Select `Query` from the `Connect` menu

<p align="center">
  <img src="select_query.png" width="600">
</p>

10. Select the database version that was imported (wait until the data are loaded ~ 30 seconds)

> Details about the nodes and relationships are displayed

<p align="center">
  <img src="select_db.png" width="600">
</p>

11. Display the KG schema. Type `CALL apoc.meta.graph()` in the query dialog box

> Drag the nodes to rearange them

<p align="center">
  <img src="display_schema.png" width="1000">
</p>
