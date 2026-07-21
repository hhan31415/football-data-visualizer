# Parses a raw NCAA.com multi-table stat export (concatenated leaderboard
# pages) into one tidy wide data frame: one row per team, one column per stat.
#
# Usage:
#   source("clean_ncaa_stats.R")
#   df <- clean_ncaa_stats("team_rankings.csv")
#   write.csv(df, "ncaa_di_mens_soccer_team_stats_clean.csv", row.names = FALSE)

library(stringr)

# Which columns to keep from each stat page, and what to rename them to.
# Only the *unique* metric from each page is kept -- shared context columns
# (Team Games, W-L, raw Goals/Assists repeated across pages) are deduped.
keep_map <- list(
  "Corner Kicks Per Game"       = c(Corners = "Corners", `Per Game` = "CornersPerGame"),
  "Red Cards"                   = c(`Red Cards` = "RedCards"),
  "Yellow Cards"                = c(`Yellow Cards` = "YellowCards"),
  "Scoring Offense"             = c(`Per Game` = "GoalsPerGame"),
  "Total Goals"                 = c(Goals = "TotalGoals", `Team Games` = "Games"),
  "Team Goals Against Average"  = c(`Team Min` = "TeamMinutes", GA = "GoalsAgainst", GAA = "GAA"),
  "Shutout Percentage"          = c(Shutouts = "Shutouts", `Per Game` = "ShutoutPct"),
  "Won-Lost-Tied Percentage"    = c(Won = "Wins", Loss = "Losses", Tied = "Ties", `Pct.` = "WinPct"),
  "Penalty Kicks"               = c(PS = "PKGoals", psatt = "PKAttempts", `Pct.` = "PKPct"),
  "Goal Differential"           = c(Diff = "GoalDiff"),
  "Shot Accuracy"               = c(SoG = "ShotsOnGoal", ShAtt = "ShotAttempts", `Pct.` = "ShotAccuracyPct"),
  "Saves Per Game"              = c(Saves = "TotalSaves", `Per Game` = "SavesPerGame"),
  "Shots on Goal Per Game"      = c(`Per Game` = "ShotsOnGoalPerGame"),
  "Total Points"                = c(Points = "TotalPoints"),
  "Shots Per Game"              = c(`Per Game` = "ShotsPerGame"),
  "Fouls Per Game"              = c(Fouls = "TotalFouls", `Per Game` = "FoulsPerGame"),
  "Assists Per Game"            = c(`Per Game` = "AssistsPerGame"),
  "Total Assists"               = c(Assists = "TotalAssists"),
  "Points Per Game"             = c(`Per Game` = "PointsPerGame"),
  "Save Pct"                    = c(`Pct.` = "SavePct")
)

clean_ncaa_stats <- function(path) {
  raw <- readLines(path, warn = FALSE)

  is_header_row <- function(l) str_starts(str_trim(l), '"Rank","Name"')
  is_category_marker <- function(l) str_trim(l) %in% c("NCAA Men's Soccer", "NCAA Women's Soccer")

  blocks <- list()
  i <- 1
  n <- length(raw)
  current_category <- NULL

  while (i <= n) {
    line <- raw[i]

    if (is_category_marker(line)) {
      i <- i + 1
      if (i <= n) {
        cat_line <- str_trim(raw[i])
        current_category <- str_replace(cat_line, "^Division\\s+[IVX]+", "") |> str_trim()
      }
      i <- i + 1
      next
    }

    if (is_header_row(line)) {
      header <- as.character(read.csv(text = line, header = FALSE, stringsAsFactors = FALSE))
      j <- i + 1
      row_lines <- c()
      while (j <= n) {
        l2 <- str_trim(raw[j])
        if (l2 == "" || is_category_marker(raw[j]) ||
            l2 == "Reclassifying" || str_starts(l2, "<script") ||
            str_starts(l2, "var ") || str_starts(l2, "try")) break
        row_lines <- c(row_lines, raw[j])
        j <- j + 1
      }
      if (length(row_lines) > 0) {
        df <- read.csv(text = row_lines, header = FALSE, stringsAsFactors = FALSE,
                        col.names = header, colClasses = "character")
        blocks[[length(blocks) + 1]] <- list(category = current_category, data = df)
      }
      i <- j
      next
    }
    i <- i + 1
  }

  # Merge all blocks on team Name into one wide table
  teams <- list()
  for (b in blocks) {
    cols <- keep_map[[b$category]]
    if (is.null(cols)) next
    df <- b$data
    for (r in seq_len(nrow(df))) {
      team <- str_trim(df$Name[r])
      if (is.null(teams[[team]])) teams[[team]] <- list()
      for (src in names(cols)) {
        if (src %in% names(df)) {
          teams[[team]][[cols[src]]] <- df[[src]][r]
        }
      }
    }
  }

  final_cols <- c("Team","Games","Wins","Losses","Ties","WinPct",
    "TotalGoals","GoalsPerGame","TotalAssists","AssistsPerGame",
    "TotalPoints","PointsPerGame","GoalDiff",
    "ShotAttempts","ShotsPerGame","ShotsOnGoal","ShotsOnGoalPerGame",
    "ShotAccuracyPct","Corners","CornersPerGame",
    "PKGoals","PKAttempts","PKPct",
    "TotalFouls","FoulsPerGame","YellowCards","RedCards",
    "TotalSaves","SavesPerGame","SavePct",
    "TeamMinutes","GoalsAgainst","GAA","Shutouts","ShutoutPct")

  out <- do.call(rbind, lapply(names(teams), function(team) {
    row <- teams[[team]]
    vals <- sapply(final_cols[-1], function(c) if (is.null(row[[c]])) NA else row[[c]])
    data.frame(Team = team, t(vals), stringsAsFactors = FALSE, check.names = FALSE)
  }))
  colnames(out) <- final_cols

  # Red card leaderboard omits teams with 0 -- NA there really means zero
  out$RedCards[is.na(out$RedCards)] <- "0"

  # Convert numeric-looking columns
  numeric_cols <- setdiff(final_cols, "Team")
  out[numeric_cols] <- lapply(out[numeric_cols], function(x) suppressWarnings(as.numeric(x)))

  out
}
