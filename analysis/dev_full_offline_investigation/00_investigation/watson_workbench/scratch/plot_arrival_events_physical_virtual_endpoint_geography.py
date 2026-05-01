from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve
import zipfile

import duckdb
import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"

ARRIVAL_ROOT = RUN_ROOT / "data" / "layer2" / "5B" / "arrival_events"
SITE_LOCATIONS_ROOT = RUN_ROOT / "data" / "layer1" / "1B" / "site_locations"
EDGE_CATALOGUE_ROOT = RUN_ROOT / "data" / "layer1" / "3B" / "edge_catalogue"
VIRTUAL_SETTLEMENT_ROOT = RUN_ROOT / "data" / "layer1" / "3B" / "virtual_settlement"

EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "traffic_primitives"
    / "branches"
    / "physical_virtual_routing"
    / "endpoint_geography"
)
FIGURE_DIR = EXPORT_DIR / "figures"
REFERENCE_DIR = EXPORT_DIR / "reference"
NATURAL_EARTH_URL = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"


COLORS = {
    "ink": "#292724",
    "grid": "#d9d2c3",
    "paper": "#fbf7ef",
    "blue": "#1f4e5f",
    "rust": "#b86b42",
    "gold": "#c9a227",
    "green": "#6d8f71",
    "slate": "#5d6d7e",
    "plum": "#7b3f61",
}


def parquet_pattern(path: Path) -> str:
    return str(path / "**" / "*.parquet").replace("\\", "/")


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": COLORS["paper"],
            "axes.facecolor": COLORS["paper"],
            "axes.edgecolor": COLORS["ink"],
            "axes.labelcolor": COLORS["ink"],
            "xtick.color": COLORS["ink"],
            "ytick.color": COLORS["ink"],
            "text.color": COLORS["ink"],
            "axes.titleweight": "bold",
        }
    )


def style_geo_axes(ax: plt.Axes, title: str) -> None:
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 85)
    ax.set_xticks(np.arange(-180, 181, 60))
    ax.set_yticks(np.arange(-60, 91, 30))
    ax.grid(color=COLORS["grid"], linewidth=0.8, alpha=0.72)
    ax.set_axisbelow(True)
    ax.axhline(0, color=COLORS["grid"], linewidth=1.1)
    ax.axvline(0, color=COLORS["grid"], linewidth=1.1)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title, loc="left", fontsize=11, pad=12)


def add_info_box(ax: plt.Axes, text: str, loc: tuple[float, float] = (0.02, 0.96)) -> None:
    ax.text(
        loc[0],
        loc[1],
        text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": COLORS["paper"], "edgecolor": COLORS["grid"]},
    )


def style_axes(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color=COLORS["grid"], linewidth=0.8, alpha=0.72)
    ax.set_axisbelow(True)


def compact_int(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def savefig(name: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIGURE_DIR / name, dpi=180, bbox_inches="tight")
    plt.close()


def load_world_boundaries() -> gpd.GeoDataFrame | None:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = REFERENCE_DIR / "ne_110m_admin_0_countries.zip"
    extract_dir = REFERENCE_DIR / "ne_110m_admin_0_countries"
    shp_path = extract_dir / "ne_110m_admin_0_countries.shp"

    if not shp_path.exists():
        try:
            if not zip_path.exists():
                urlretrieve(NATURAL_EARTH_URL, zip_path)
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_dir)
        except Exception as exc:
            print(f"WARNING: could not load Natural Earth boundaries: {exc}")
            return None

    return gpd.read_file(shp_path)


def plot_basemap(ax: plt.Axes, extent: tuple[float, float, float, float]) -> None:
    world = load_world_boundaries()
    if world is not None:
        min_lon, max_lon, min_lat, max_lat = extent
        subset = world.cx[min_lon:max_lon, min_lat:max_lat]
        subset.plot(ax=ax, color="#efe4d2", edgecolor="#b7ad9c", linewidth=0.55, zorder=0)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.grid(color=COLORS["grid"], linewidth=0.8, alpha=0.58)
    ax.set_axisbelow(True)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_facecolor("#f6efe3")


def build_compact_evidence() -> dict[str, pd.DataFrame]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    arrivals = parquet_pattern(ARRIVAL_ROOT)
    sites = parquet_pattern(SITE_LOCATIONS_ROOT)
    edges = parquet_pattern(EDGE_CATALOGUE_ROOT)
    settlements = parquet_pattern(VIRTUAL_SETTLEMENT_ROOT)

    # Select one physical merchant with a visible multi-country site footprint and
    # one virtual merchant near the median edge count. The route mode is
    # merchant-stable, so no single merchant demonstrates both site and edge estate
    # in this arrival surface.
    physical_candidates = con.execute(
        f"""
        WITH arrival_physical AS (
            SELECT
                merchant_id,
                COUNT(*) AS arrival_rows,
                COUNT(DISTINCT site_id) AS arrival_site_ids
            FROM read_parquet('{arrivals}', hive_partitioning=true)
            WHERE is_virtual = false
            GROUP BY 1
        ),
        site_counts AS (
            SELECT
                merchant_id,
                COUNT(*) AS site_locations,
                COUNT(DISTINCT legal_country_iso) AS site_countries,
                MAX(lon_deg) - MIN(lon_deg) AS lon_span,
                MAX(lat_deg) - MIN(lat_deg) AS lat_span
            FROM read_parquet('{sites}', hive_partitioning=true)
            GROUP BY 1
        )
        SELECT
            p.merchant_id,
            p.arrival_rows,
            p.arrival_site_ids,
            s.site_locations,
            s.site_countries,
            s.lon_span,
            s.lat_span
        FROM arrival_physical p
        INNER JOIN site_counts s USING (merchant_id)
        WHERE s.site_locations BETWEEN 15 AND 35
        ORDER BY
            s.site_countries DESC,
            (s.lon_span + s.lat_span) DESC,
            ABS(s.site_locations - 17),
            ABS(p.arrival_rows - 34690),
            p.merchant_id
        LIMIT 1
        """
    ).fetchdf()

    virtual_candidates = con.execute(
        f"""
        WITH arrival_virtual AS (
            SELECT
                merchant_id,
                COUNT(*) AS arrival_rows,
                COUNT(DISTINCT edge_id) AS arrival_edge_ids
            FROM read_parquet('{arrivals}', hive_partitioning=true)
            WHERE is_virtual = true
            GROUP BY 1
        ),
        edge_counts AS (
            SELECT
                merchant_id,
                COUNT(*) AS catalogue_edges,
                COUNT(DISTINCT country_iso) AS edge_countries
            FROM read_parquet('{edges}', hive_partitioning=true)
            GROUP BY 1
        )
        SELECT
            v.merchant_id,
            v.arrival_rows,
            v.arrival_edge_ids,
            e.catalogue_edges,
            e.edge_countries
        FROM arrival_virtual v
        INNER JOIN edge_counts e USING (merchant_id)
        ORDER BY
            ABS(e.catalogue_edges - 18),
            ABS(v.arrival_rows - 95103),
            v.merchant_id
        LIMIT 1
        """
    ).fetchdf()

    physical_merchant = int(physical_candidates["merchant_id"].iloc[0])
    virtual_merchant = int(virtual_candidates["merchant_id"].iloc[0])

    physical_sites = con.execute(
        f"""
        SELECT
            merchant_id,
            legal_country_iso,
            site_order,
            lon_deg,
            lat_deg
        FROM read_parquet('{sites}', hive_partitioning=true)
        WHERE merchant_id = {physical_merchant}
        ORDER BY legal_country_iso, site_order
        """
    ).fetchdf()

    virtual_edges = con.execute(
        f"""
        SELECT
            merchant_id,
            edge_id,
            edge_seq_index,
            country_iso,
            lon_deg,
            lat_deg,
            tzid_operational,
            edge_weight
        FROM read_parquet('{edges}', hive_partitioning=true)
        WHERE merchant_id = {virtual_merchant}
        ORDER BY edge_seq_index
        """
    ).fetchdf()

    virtual_settlement = con.execute(
        f"""
        SELECT
            merchant_id,
            settlement_site_id,
            lon_deg,
            lat_deg,
            tzid_settlement,
            coord_source_id
        FROM read_parquet('{settlements}', hive_partitioning=true)
        WHERE merchant_id = {virtual_merchant}
        ORDER BY settlement_site_id
        """
    ).fetchdf()

    endpoint_counts = con.execute(
        f"""
        WITH arrival_physical AS (
            SELECT merchant_id
            FROM read_parquet('{arrivals}', hive_partitioning=true)
            WHERE is_virtual = false
            GROUP BY 1
        ),
        arrival_virtual AS (
            SELECT merchant_id
            FROM read_parquet('{arrivals}', hive_partitioning=true)
            WHERE is_virtual = true
            GROUP BY 1
        ),
        physical_counts AS (
            SELECT
                'physical site estate' AS endpoint_estate,
                s.merchant_id,
                COUNT(*) AS endpoint_count
            FROM read_parquet('{sites}', hive_partitioning=true) s
            INNER JOIN arrival_physical p USING (merchant_id)
            GROUP BY 1, 2
        ),
        virtual_counts AS (
            SELECT
                'virtual edge estate' AS endpoint_estate,
                e.merchant_id,
                COUNT(*) AS endpoint_count
            FROM read_parquet('{edges}', hive_partitioning=true) e
            INNER JOIN arrival_virtual v USING (merchant_id)
            GROUP BY 1, 2
        )
        SELECT * FROM physical_counts
        UNION ALL
        SELECT * FROM virtual_counts
        """
    ).fetchdf()

    selected = pd.concat(
        [
            physical_candidates.assign(route_mode="physical", selected_for="representative physical site estate"),
            virtual_candidates.assign(route_mode="virtual", selected_for="representative virtual edge estate"),
        ],
        ignore_index=True,
        sort=False,
    )

    selected.to_csv(EXPORT_DIR / "selected_endpoint_merchants.csv", index=False)
    physical_sites.to_csv(EXPORT_DIR / "representative_physical_merchant_sites.csv", index=False)
    virtual_edges.to_csv(EXPORT_DIR / "representative_virtual_merchant_edges.csv", index=False)
    virtual_settlement.to_csv(EXPORT_DIR / "representative_virtual_merchant_settlement.csv", index=False)
    endpoint_counts.to_csv(EXPORT_DIR / "endpoint_counts_by_route_merchant.csv", index=False)

    return {
        "selected": selected,
        "physical_sites": physical_sites,
        "virtual_edges": virtual_edges,
        "virtual_settlement": virtual_settlement,
        "endpoint_counts": endpoint_counts,
    }


def plot_representative_endpoint_geography(data: dict[str, pd.DataFrame]) -> None:
    selected = data["selected"].copy()
    physical_sites = data["physical_sites"].copy()
    virtual_edges = data["virtual_edges"].copy()
    virtual_settlement = data["virtual_settlement"].copy()

    physical_meta = selected.loc[selected["route_mode"].eq("physical")].iloc[0]
    virtual_meta = selected.loc[selected["route_mode"].eq("virtual")].iloc[0]

    fig, axes = plt.subplots(1, 2, figsize=(15.2, 6.0), sharex=True, sharey=True)
    fig.suptitle("Physical Sites and Virtual Edges Are Both Geographic, but They Are Different Operating Objects", fontsize=14.0, y=1.01)

    ax = axes[0]
    style_geo_axes(ax, "Physical route: outlet/site coordinates")
    ax.scatter(
        physical_sites["lon_deg"],
        physical_sites["lat_deg"],
        s=92,
        color=COLORS["green"],
        edgecolors=COLORS["ink"],
        linewidths=0.7,
        alpha=0.92,
        label="site location",
    )
    add_info_box(
        ax,
        f"merchant_id: {int(physical_meta['merchant_id'])}\n"
        f"sites: {len(physical_sites):,}\n"
        f"site countries: {physical_sites['legal_country_iso'].nunique():,}\n"
        f"arrival rows: {int(physical_meta['arrival_rows']):,}",
    )
    for _, row in physical_sites.drop_duplicates("legal_country_iso").head(8).iterrows():
        ax.text(row["lon_deg"] + 2, row["lat_deg"] + 1.5, str(row["legal_country_iso"]), fontsize=8)
    ax.legend(frameon=False, loc="lower left")

    ax = axes[1]
    style_geo_axes(ax, "Virtual route: operational edge coordinates")
    sizes = 70 + (virtual_edges["edge_weight"] / virtual_edges["edge_weight"].max()) * 230
    ax.scatter(
        virtual_edges["lon_deg"],
        virtual_edges["lat_deg"],
        s=sizes,
        color=COLORS["gold"],
        edgecolors=COLORS["ink"],
        linewidths=0.65,
        alpha=0.9,
        label="operational edge",
    )
    if not virtual_settlement.empty:
        ax.scatter(
            virtual_settlement["lon_deg"],
            virtual_settlement["lat_deg"],
            s=260,
            marker="*",
            color=COLORS["plum"],
            edgecolors=COLORS["ink"],
            linewidths=0.8,
            label="settlement anchor",
            zorder=4,
        )
    add_info_box(
        ax,
        f"merchant_id: {int(virtual_meta['merchant_id'])}\n"
        f"edges: {len(virtual_edges):,}\n"
        f"edge countries: {virtual_edges['country_iso'].nunique():,}\n"
        f"arrival rows: {int(virtual_meta['arrival_rows']):,}\n"
        f"settlement anchors: {len(virtual_settlement):,}",
    )
    for _, row in virtual_edges.drop_duplicates("country_iso").head(8).iterrows():
        ax.text(row["lon_deg"] + 2, row["lat_deg"] + 1.5, str(row["country_iso"]), fontsize=8)
    ax.legend(frameon=False, loc="lower left")

    fig.tight_layout()
    savefig("01_representative_endpoint_geography.png")


def plot_virtual_edge_network_anchor(data: dict[str, pd.DataFrame]) -> None:
    selected = data["selected"].copy()
    virtual_edges = data["virtual_edges"].copy()
    virtual_settlement = data["virtual_settlement"].copy()
    virtual_meta = selected.loc[selected["route_mode"].eq("virtual")].iloc[0]

    coord_frames = [virtual_edges[["lon_deg", "lat_deg"]]]
    if not virtual_settlement.empty:
        coord_frames.append(virtual_settlement[["lon_deg", "lat_deg"]])
    coords = pd.concat(coord_frames, ignore_index=True)
    lon_margin = max(8.0, (coords["lon_deg"].max() - coords["lon_deg"].min()) * 0.08)
    lat_margin = max(6.0, (coords["lat_deg"].max() - coords["lat_deg"].min()) * 0.12)
    extent = (
        max(-180.0, coords["lon_deg"].min() - lon_margin),
        min(180.0, coords["lon_deg"].max() + lon_margin),
        max(-60.0, coords["lat_deg"].min() - lat_margin),
        min(85.0, coords["lat_deg"].max() + lat_margin),
    )

    fig, ax = plt.subplots(figsize=(11.8, 6.8))
    plot_basemap(ax, extent)
    ax.set_title("Virtual routing: operational edge map versus settlement anchor", loc="left", fontsize=13, pad=12)

    if not virtual_settlement.empty:
        anchor = virtual_settlement.iloc[0]
        for _, edge in virtual_edges.iterrows():
            ax.plot(
                [anchor["lon_deg"], edge["lon_deg"]],
                [anchor["lat_deg"], edge["lat_deg"]],
                color=COLORS["slate"],
                linewidth=0.75,
                alpha=0.32,
                zorder=2,
            )
        ax.scatter(
            [anchor["lon_deg"]],
            [anchor["lat_deg"]],
            s=310,
            marker="*",
            color=COLORS["plum"],
            edgecolors=COLORS["ink"],
            linewidths=0.8,
            label=f"settlement anchor ({anchor['tzid_settlement']})",
            zorder=5,
        )

    sizes = 70 + (virtual_edges["edge_weight"] / virtual_edges["edge_weight"].max()) * 240
    ax.scatter(
        virtual_edges["lon_deg"],
        virtual_edges["lat_deg"],
        s=sizes,
        color=COLORS["gold"],
        edgecolors=COLORS["ink"],
        linewidths=0.65,
        alpha=0.92,
        label="operational edges",
        zorder=4,
    )
    top_labels = virtual_edges.sort_values("edge_weight", ascending=False).head(8)
    for _, edge in top_labels.iterrows():
        ax.text(
            edge["lon_deg"] + 1.8,
            edge["lat_deg"] + 1.0,
            str(edge["country_iso"]),
            fontsize=8,
            zorder=6,
            bbox={"boxstyle": "round,pad=0.12", "facecolor": COLORS["paper"], "edgecolor": "none", "alpha": 0.78},
        )
    add_info_box(
        ax,
        f"merchant_id: {int(virtual_meta['merchant_id'])}\n"
        f"edges: {len(virtual_edges):,}\n"
        f"edge countries: {virtual_edges['country_iso'].nunique():,}\n"
        f"settlement anchor: {virtual_settlement['tzid_settlement'].iloc[0] if not virtual_settlement.empty else 'missing'}",
    )
    ax.legend(frameon=False, loc="lower left", ncol=2)
    fig.tight_layout()
    savefig("02_virtual_edge_network_anchor.png")


def plot_endpoint_count_distribution(data: dict[str, pd.DataFrame]) -> None:
    endpoint_counts = data["endpoint_counts"].copy()
    selected = data["selected"].copy()

    physical_id = int(selected.loc[selected["route_mode"].eq("physical"), "merchant_id"].iloc[0])
    virtual_id = int(selected.loc[selected["route_mode"].eq("virtual"), "merchant_id"].iloc[0])

    fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.4), sharey=False)
    fig.suptitle("Virtual Merchants Also Have Endpoint Estates, Not a Single Abstract Store", fontsize=14.5, y=1.03)

    for ax, estate, color, selected_id, label in [
        (axes[0], "physical site estate", COLORS["green"], physical_id, "physical sites per merchant"),
        (axes[1], "virtual edge estate", COLORS["gold"], virtual_id, "virtual edges per merchant"),
    ]:
        subset = endpoint_counts.loc[endpoint_counts["endpoint_estate"].eq(estate)].copy()
        bins = np.arange(0, subset["endpoint_count"].max() + 5, 5)
        ax.hist(subset["endpoint_count"], bins=bins, color=color, edgecolor="none", alpha=0.92)
        selected_count = int(subset.loc[subset["merchant_id"].eq(selected_id), "endpoint_count"].iloc[0])
        ax.axvline(selected_count, color=COLORS["ink"], linewidth=2.0, linestyle="--", label=f"selected merchant: {selected_count}")
        ax.axvline(subset["endpoint_count"].median(), color=COLORS["rust"], linewidth=2.0, linestyle=":", label=f"median: {subset['endpoint_count'].median():.0f}")
        ax.set_xlabel(label)
        ax.set_ylabel("Merchants")
        ax.set_title(estate)
        ax.legend(frameon=False)
        style_axes(ax)
        ax.text(
            0.02,
            0.94,
            f"merchants: {len(subset):,}\nmin/median/max: {int(subset['endpoint_count'].min())}/{subset['endpoint_count'].median():.0f}/{int(subset['endpoint_count'].max())}",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": COLORS["paper"], "edgecolor": COLORS["grid"]},
        )

    fig.tight_layout()
    savefig("03_endpoint_count_distribution.png")


def main() -> None:
    apply_style()
    data = build_compact_evidence()
    plot_representative_endpoint_geography(data)
    plot_virtual_edge_network_anchor(data)
    plot_endpoint_count_distribution(data)
    selected = data["selected"][
        [
            "route_mode",
            "merchant_id",
            "arrival_rows",
            "arrival_site_ids",
            "site_locations",
            "arrival_edge_ids",
            "catalogue_edges",
            "edge_countries",
        ]
    ]
    print(selected.to_string(index=False))
    print(f"Figures written to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
