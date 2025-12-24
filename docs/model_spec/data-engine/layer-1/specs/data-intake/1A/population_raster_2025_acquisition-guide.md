# Acquisition Guide — `population_raster_2025` (Global population counts raster, COG GeoTIFF)

## 0) Purpose and role in the engine

`population_raster_2025` is a **pinned population surface** used as a **spatial prior** (notably by **1B** for outlet placement realism). It must be **stable, global, and reasonably sized**.

This should **not** be an OSM planet download (no 35–56GB surprises).

---

## 1) Engine requirements (MUST)

### 1.1 Identity

* **Dataset ID:** `population_raster_2025`
* **Version:** `2025`
* **Format:** `tif` (**Cloud-Optimized GeoTIFF / COG**)
* **Path:** `reference/spatial/population/2025/population.tif`

### 1.2 Raster semantics (MUST)

* Values represent **estimated number of people per pixel** (population counts).
* CRS must be **WGS84 / EPSG:4326**.
* Resolution target: **30 arc-seconds (~1km)** is acceptable for “priors” and keeps files small. ([hub.worldpop.org][1])

---

## 2) Recommended source (small + versioned)

### Primary source (PINNED): WorldPop Global 2015–2030, **R2025A v1**, 1km, constrained, year 2025

WorldPop publishes a **global 1km constrained** population count GeoTIFF for 2025. The file is explicitly listed at **~276MB**, so you’re not going to hit multi-GB/planet-scale territory. ([data.worldpop.org][2])

**What you will download**

* Filename: `global_pop_2025_CN_1km_R2025A_v1.tif`
* Size: `276M` ([data.worldpop.org][2])

WorldPop describes this product as:

* 2025 population distribution
* GeoTIFF
* ~1km (30 arc-seconds)
* WGS84
* units: people per pixel ([hub.worldpop.org][1])

---

## 3) Acquisition method (download)

### 3.1 Direct download (PINNED)

Download the exact file from WorldPop’s public directory index:

* **Directory index:** ([data.worldpop.org][2])
* **Direct file URL (copy/paste):**

```text
https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/0_Mosaicked/v1/1km/constrained/global_pop_2025_CN_1km_R2025A_v1.tif
```

### 3.2 Release statement (metadata evidence)

Keep the release statement PDF pinned in provenance:

```text
https://data.worldpop.org/repo/prj/Global_2015_2030/R2025A/doc/Global2_Release_Statement_R2025A_v1.pdf
```

This release is explicitly described as an **alpha public release** that may change as improvements are made. 

---

## 4) Size / coverage expectations (so you don’t get burned)

### 4.1 Why this won’t explode

* You are downloading **one global 1km GeoTIFF** (~276MB). ([data.worldpop.org][2])
* Avoid the **100m global** products unless you genuinely need them; those are the ones that can balloon.

### 4.2 Spatial coverage / NoData (MUST account for)

WorldPop’s Global2 production describes a land-focused “mastergrid” and notes oceans/major inland water as NoData; the mastergrid coverage is described as between ~84°N and 60°S. 
Implication: your engine must treat NoData/water as **non-habitable** (weight 0).

---

## 5) Shaping rules (Codex implements; this doc specifies)

### 5.1 Output must be a COG (MUST)

Even if the source is a plain GeoTIFF, your engine contract wants a **COG** at:

* `reference/spatial/population/2025/population.tif`

COG requirements (minimal):

* internal tiling
* overviews (pyramids)
* lossless or controlled compression
* CRS preserved as EPSG:4326

### 5.2 Value + NoData handling (MUST)

* Preserve “people per pixel” values as provided.
* Preserve NoData, or convert NoData to 0 **with an explicit provenance note** (either is acceptable as long as downstream semantics are consistent).

### 5.3 Determinism (MUST)

* The produced file must be byte-stable given the same source + same conversion options.
* Record conversion tool + options in provenance.

---

## 6) Licensing (MUST record correctly)

WorldPop states a general **CC BY 4.0** licence for its datasets. ([WorldPop][3])
It also states that datasets **derived from OpenStreetMap and/or Microsoft Building Footprints/Roads Detection** are under **ODbL**. ([hub.worldpop.org][1])
The R2025A release statement lists **Microsoft Building Footprints** as an input to settlement modelling, which is why you should treat licensing carefully. 

**Actionable rule for now (PINNED):**

* Record licence as **ODbL** in your provenance unless you can confirm (from WorldPop’s own release metadata for this specific file) that it is CC BY only.

---

## 7) Engine-fit validation checklist (MUST pass)

* File exists at: `reference/spatial/population/2025/population.tif`
* GeoTIFF opens successfully (GDAL-readable)
* CRS = EPSG:4326
* Resolution is ~30 arc-seconds (~1km) ([hub.worldpop.org][1])
* Pixel values are finite and non-negative
* NoData is handled consistently (preserved or mapped to 0)
* COG compliance checks pass (tiling + overviews)

---

## 8) Provenance sidecar (MANDATORY)

Write a sidecar next to the output file containing:

* Source URL (direct .tif link) ([data.worldpop.org][2])
* Downloaded_at_utc
* Raw sha256
* Output sha256
* Release statement URL + sha256 
* Conversion tool + options (for COG)
* Licence recorded + attribution text

---

## 9) Working links (copy/paste)

```text
# WorldPop dataset index (lets you browse the exact R2025A/2025 mosaic)
https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/0_Mosaicked/v1/1km/constrained/

# Direct file (the one you actually want)
https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/0_Mosaicked/v1/1km/constrained/global_pop_2025_CN_1km_R2025A_v1.tif

# WorldPop geodata summary page for the 2025 global 1km product (metadata + “alpha” note)
https://hub.worldpop.org/geodata/summary?id=80031

# Release statement (methodology + production notes)
https://data.worldpop.org/repo/prj/Global_2015_2030/R2025A/doc/Global2_Release_Statement_R2025A_v1.pdf

# WorldPop licence FAQ (CC BY 4.0 statement)
https://www.worldpop.org/faq/
```

---

[1]: https://hub.worldpop.org/geodata/summary?id=80031 "WorldPop :: Population Counts"
[2]: https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/0_Mosaicked/v1/1km/constrained/ "Index of /GIS/Population/Global_2015_2030/R2025A/2025/0_Mosaicked/v1/1km/constrained"
[3]: https://www.worldpop.org/faq/?utm_source=chatgpt.com "faq"
