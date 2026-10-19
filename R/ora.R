#!/usr/bin/env Rscript
# Enrichment bridge for reproducible-network-pharmacology.
#
# Contract:  Rscript R/ora.R <input.json> [output_dir]
# Schema:    schemas/enrichment_input.schema.json
# Outputs:   enrichment_result.tsv   (complete tested-term table)
#            entrez_to_symbol.tsv
#            enrichment_meta.json
#
# Design notes:
# * The Python side owns orchestration and provenance; this script owns the
#   statistics and reports its own package versions so a run can be reproduced.
# * The complete tested-term table is always written: the analysis is computed
#   with pvalueCutoff = qvalueCutoff = 1 and the caller applies display cutoffs.
#   "No significant term" is therefore a property of the complete table, not a
#   missing-file accident.
# * An explicit background that cannot be mapped is a hard error (exit 2); it is
#   never replaced by the default annotated genome.
# * Gene IDs stay as ENTREZID in the result table; symbol mapping is exported
#   separately so downstream tables do not depend on a display convention.
# * KEGG needs network access and is subject to KEGG's own license; GO is offline
#   via the OrgDb annotation package.
# * synthetic_gene_sets (optional) runs clusterProfiler::enricher on frozen sets;
#   it exists for an independent hypergeometric/BH benchmark, not for science.

suppressPackageStartupMessages({
  ok <- requireNamespace("jsonlite", quietly = TRUE)
})
if (!ok) {
  message("error: the R package 'jsonlite' is required")
  quit(save = "no", status = 2L)
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1L) {
  message("usage: Rscript R/ora.R <input.json> [output_dir]")
  quit(save = "no", status = 2L)
}
input_path <- args[[1]]
if (!file.exists(input_path)) {
  message("error: input not found: ", input_path)
  quit(save = "no", status = 2L)
}
cfg <- tryCatch(
  jsonlite::fromJSON(input_path, simplifyVector = TRUE),
  error = function(e) {
    message("error: cannot parse ", input_path, ": ", conditionMessage(e))
    quit(save = "no", status = 2L)
  }
)
required <- c("genes", "gene_id_type", "species", "gene_sets", "output_dir")
missing_fields <- setdiff(required, names(cfg))
if (length(missing_fields) > 0L) {
  message("error: missing fields: ", paste(missing_fields, collapse = ", "))
  quit(save = "no", status = 2L)
}

genes <- unique(trimws(as.character(cfg$genes)))
genes <- genes[nzchar(genes)]
if (length(genes) == 0L) {
  message("error: no genes provided")
  quit(save = "no", status = 2L)
}

output_dir <- if (length(args) >= 2L) args[[2]] else cfg$output_dir
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

package_version_or_na <- function(package) {
  if (requireNamespace(package, quietly = TRUE)) {
    as.character(utils::packageVersion(package))
  } else {
    NA_character_
  }
}

param <- function(name, default) {
  value <- cfg[[name]]
  if (is.null(value)) default else value
}
requested_p_adjust <- param("p_adjust", "BH")
requested_pvalue <- as.numeric(param("pvalue_cutoff", 0.05))
requested_qvalue <- as.numeric(param("qvalue_cutoff", 0.20))
min_gssize <- as.integer(param("min_gssize", 10L))
max_gssize <- as.integer(param("max_gssize", 500L))
key_type <- cfg$gene_id_type
gene_sets <- cfg$gene_sets

species_map <- list(
  Homo_sapiens = list(orgdb = "org.Hs.eg.db", organism = "hsa"),
  Mus_musculus = list(orgdb = "org.Mm.eg.db", organism = "mmu")
)
species <- species_map[[cfg$species]]
if (is.null(species)) {
  message("error: unsupported species: ", cfg$species)
  quit(save = "no", status = 2L)
}
if (!requireNamespace(species$orgdb, quietly = TRUE)) {
  message("error: missing annotation package: ", species$orgdb)
  quit(save = "no", status = 2L)
}
if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
  message("error: missing R package: clusterProfiler (install via BiocManager)")
  quit(save = "no", status = 2L)
}
orgdb <- getExportedValue(species$orgdb, species$orgdb)

# ---- foreground mapping ----------------------------------------------------
mapping <- data.frame(SYMBOL = character(0), ENTREZID = character(0))
unmapped <- character(0)
if (key_type == "SYMBOL") {
  mapped <- suppressWarnings(tryCatch(
    clusterProfiler::bitr(genes, fromType = "SYMBOL", toType = "ENTREZID", OrgDb = orgdb),
    error = function(e) NULL
  ))
  if (!is.null(mapped) && nrow(mapped) > 0L) {
    mapping <- mapped
    entrez <- unique(as.character(mapping$ENTREZID))
    unmapped <- setdiff(genes, as.character(mapping$SYMBOL))
  } else {
    entrez <- character(0)
  }
} else {
  entrez <- genes
  mapping <- data.frame(SYMBOL = genes, ENTREZID = entrez, stringsAsFactors = FALSE)
}

# ---- explicit background ---------------------------------------------------
universe <- NULL
universe_source <- "all_annotated"
universe_input <- 0L
universe_mapped <- 0L
universe_unmapped <- character(0)
if (!is.null(cfg$universe) && length(cfg$universe) > 0L) {
  universe_source <- "explicit"
  universe_genes <- unique(trimws(as.character(cfg$universe)))
  universe_genes <- universe_genes[nzchar(universe_genes)]
  universe_input <- length(universe_genes)
  if (key_type == "SYMBOL") {
    mapped_universe <- suppressWarnings(tryCatch(
      clusterProfiler::bitr(universe_genes, fromType = "SYMBOL", toType = "ENTREZID", OrgDb = orgdb),
      error = function(e) NULL
    ))
    if (!is.null(mapped_universe) && nrow(mapped_universe) > 0L) {
      universe <- unique(as.character(mapped_universe$ENTREZID))
      universe_mapped <- length(universe)
      universe_unmapped <- setdiff(universe_genes, as.character(mapped_universe$SYMBOL))
    }
  } else {
    universe <- universe_genes
    universe_mapped <- length(universe)
  }
}

write.table(
  mapping, file.path(output_dir, "entrez_to_symbol.tsv"),
  sep = "\t", quote = FALSE, row.names = FALSE, fileEncoding = "UTF-8"
)

make_meta <- function(status) {
  list(
    status = status,
    command = "Rscript R/ora.R",
    gene_sets = gene_sets,
    species = cfg$species,
    gene_id_type = key_type,
    params = list(
      p_adjust = requested_p_adjust,
      pvalue_cutoff = requested_pvalue,
      qvalue_cutoff = requested_qvalue,
      min_gssize = min_gssize,
      max_gssize = max_gssize,
      computed_pvalue_cutoff = 1,
      computed_qvalue_cutoff = 1
    ),
    counts = list(
      input = length(genes),
      mapped = length(entrez),
      unmapped = length(unmapped)
    ),
    universe = list(
      source = universe_source,
      input = universe_input,
      mapped = universe_mapped,
      unmapped = length(universe_unmapped),
      used = if (is.null(universe)) NA_integer_ else length(universe)
    ),
    unmapped_genes = head(unmapped, 100L),
    environment = list(
      r_version = paste(R.version$major, R.version$minor, sep = "."),
      platform = R.version$platform,
      packages = list(
        clusterProfiler = package_version_or_na("clusterProfiler"),
        DOSE = package_version_or_na("DOSE"),
        orgdb = package_version_or_na(species$orgdb),
        jsonlite = package_version_or_na("jsonlite")
      )
    ),
    generated_at_utc = format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ"),
    input_hash = unname(tools::md5sum(input_path))
  )
}

write_meta <- function(status, extra = list()) {
  meta <- make_meta(status)
  meta <- c(meta, extra)
  jsonlite::write_json(
    meta, file.path(output_dir, "enrichment_meta.json"),
    auto_unbox = TRUE, pretty = TRUE, digits = NA, null = "null"
  )
  invisible(meta)
}

write_empty_result <- function() {
  columns <- c(
    "ID", "Description", "GeneRatio", "BgRatio", "pvalue", "p.adjust", "qvalue",
    "geneID", "Count"
  )
  empty <- data.frame(matrix(ncol = length(columns), nrow = 0L))
  names(empty) <- columns
  write.table(
    empty, file.path(output_dir, "enrichment_result.tsv"),
    sep = "\t", quote = FALSE, row.names = FALSE, fileEncoding = "UTF-8"
  )
}

# An explicit background that cannot be mapped is a hard error: never fall back
# to the default annotated genome.
if (universe_source == "explicit" && universe_mapped == 0L) {
  write_meta("background_mapping_failed", list(
    error = "explicit background could not be mapped to any identifier"
  ))
  write_empty_result()
  message("error: explicit background could not be mapped")
  quit(save = "no", status = 2L)
}

if (length(entrez) == 0L) {
  write_empty_result()
  write_meta("no_mapped_genes")
  cat("ora: foreground mapped 0 genes; no analysis performed\n")
  quit(save = "no", status = 0L)
}

# ---- run ORA on the complete tested-term table ------------------------------
status <- "ok"
result <- NULL
synthetic <- cfg$synthetic_gene_sets
if (!is.null(synthetic) && length(synthetic) > 0L) {
  term2gene <- do.call(rbind, lapply(names(synthetic), function(term) {
    data.frame(term = term, gene = as.character(synthetic[[term]]), stringsAsFactors = FALSE)
  }))
  result <- tryCatch(
    suppressWarnings(clusterProfiler::enricher(
      gene = entrez, universe = universe, TERM2GENE = term2gene,
      pvalueCutoff = 1, qvalueCutoff = 1, pAdjustMethod = requested_p_adjust,
      minGSSize = min_gssize, maxGSSize = max_gssize
    )),
    error = function(e) {
      status <<- "analysis_failed"
      message("warning: synthetic enrichment failed: ", conditionMessage(e))
      NULL
    }
  )
  gene_sets <- "SYNTHETIC"
} else if (gene_sets == "KEGG") {
  result <- tryCatch(
    suppressWarnings(clusterProfiler::enrichKEGG(
      gene = entrez, organism = species$organism, keyType = "kegg",
      pvalueCutoff = 1, qvalueCutoff = 1, pAdjustMethod = requested_p_adjust,
      minGSSize = min_gssize, maxGSSize = max_gssize, universe = universe
    )),
    error = function(e) {
      status <<- "kegg_unavailable"
      message("warning: KEGG enrichment failed: ", conditionMessage(e))
      NULL
    }
  )
} else {
  ont <- sub("^GO_", "", gene_sets)
  result <- tryCatch(
    suppressWarnings(clusterProfiler::enrichGO(
      gene = entrez, OrgDb = orgdb, keyType = "ENTREZID", ont = ont,
      pvalueCutoff = 1, qvalueCutoff = 1, pAdjustMethod = requested_p_adjust,
      minGSSize = min_gssize, maxGSSize = max_gssize,
      universe = universe, readable = FALSE
    )),
    error = function(e) {
      status <<- "analysis_failed"
      message("warning: GO enrichment failed: ", conditionMessage(e))
      NULL
    }
  )
}

expected_columns <- c(
  "ID", "Description", "GeneRatio", "BgRatio", "pvalue", "p.adjust", "qvalue",
  "geneID", "Count"
)
if (is.null(result)) {
  frame <- data.frame(matrix(ncol = length(expected_columns), nrow = 0L))
  names(frame) <- expected_columns
} else {
  frame <- as.data.frame(result)
  if (nrow(frame) > 0L) frame <- frame[order(frame$p.adjust, frame$ID), , drop = FALSE]
  for (column in setdiff(expected_columns, names(frame))) frame[[column]] <- NA
  frame <- frame[, expected_columns, drop = FALSE]
}
write.table(
  frame, file.path(output_dir, "enrichment_result.tsv"),
  sep = "\t", quote = FALSE, row.names = FALSE, fileEncoding = "UTF-8", na = ""
)
write_meta(status, list(counts = c(
  make_meta(status)$counts,
  list(terms_tested = nrow(frame))
)))

cat(sprintf(
  "ora: %d genes -> %d mapped, %d tested term(s), status=%s\n",
  length(genes), length(entrez), nrow(frame), status
))
quit(save = "no", status = 0L)
