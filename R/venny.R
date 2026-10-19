#!/usr/bin/env Rscript
# Two-set Venn diagram for an rnp intersect run.
#
# Contract: Rscript R/venny.R <venn.json> <out_dir> <group>
# Input:    venn.json written by `rnp intersect`
# Output:   <out_dir>/venn_<group>.png and .pdf
#
# The figure is a display artefact: circle areas are not proportional to set size
# and the numbers are counts, not evidence weights.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3L) {
  message("usage: Rscript R/venny.R <venn.json> <out_dir> <group>")
  quit(save = "no", status = 2L)
}
input_path <- args[[1]]
out_dir <- args[[2]]
group <- args[[3]]
if (!file.exists(input_path)) {
  message("error: input not found: ", input_path)
  quit(save = "no", status = 2L)
}
if (!requireNamespace("jsonlite", quietly = TRUE)) {
  message("error: R package 'jsonlite' is required")
  quit(save = "no", status = 2L)
}
if (!requireNamespace("VennDiagram", quietly = TRUE)) {
  message("error: R package 'VennDiagram' is required")
  quit(save = "no", status = 2L)
}

cfg <- jsonlite::fromJSON(input_path, simplifyVector = TRUE)
if (is.null(cfg$groups[[group]])) {
  message("error: unknown group: ", group)
  quit(save = "no", status = 2L)
}
targets <- as.character(cfg$groups[[group]]$targets)
disease <- as.character(cfg$groups[[group]]$disease)
if (length(targets) == 0L || length(disease) == 0L) {
  message("warning: empty set for group ", group, "; skipping plot")
  quit(save = "no", status = 0L)
}

disease_label <- if (is.null(cfg$disease_label)) "Disease" else as.character(cfg$disease_label)
sets <- list(targets, disease)
names(sets) <- c("Targets", disease_label)

dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
safe_group <- gsub("[^A-Za-z0-9_-]+", "_", group)

diagram <- VennDiagram::venn.diagram(
  x = sets,
  filename = NULL,
  fill = c("#3B6FB6", "#8C9E3F"),
  alpha = 0.30,
  lwd = 0.8,
  lty = 1,
  col = "black",
  cex = 1.2,
  cat.cex = 1.3,
  cat.col = "black",
  cat.fontface = "plain",
  margin = 0.08,
  disable.logging = TRUE
)

png_path <- file.path(out_dir, paste0("venn_", safe_group, ".png"))
pdf_path <- file.path(out_dir, paste0("venn_", safe_group, ".pdf"))

grDevices::png(png_path, width = 1800, height = 1800, res = 300)
grid::grid.newpage()
grid::grid.draw(diagram)
invisible(grDevices::dev.off())

grDevices::pdf(pdf_path, width = 6, height = 6)
grid::grid.newpage()
grid::grid.draw(diagram)
invisible(grDevices::dev.off())

cat(sprintf(
  "venn: group=%s targets=%d disease=%d intersection=%d\n",
  group, length(targets), length(disease), length(intersect(targets, disease))
))
quit(save = "no", status = 0L)
