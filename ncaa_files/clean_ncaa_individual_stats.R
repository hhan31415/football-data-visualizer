# Parses a raw NCAA.com multi-table INDIVIDUAL PLAYER stat export (concatenated
# leaderboard pages) into one tidy wide data frame: one row per player, one
# column per stat.
#
# Usage:
#   source("clean_ncaa_individual_stats.R")
#   df <- clean_ncaa_individual_stats("individual_rankings.csv")
#   write.csv(df, "ncaa_di_mens_soccer_individual_stats_clean.csv", row.names = FALSE)
#
# Note the source file is Latin-1 encoded (accented player names), not UTF-8 --
# read.csv/readLines below handle that explicitly.

library(stringr)

# ---- GLOBAL column map -------------------------------------------------
# These column NAMES mean the same thing no matter which leaderboard they
# appear on (e.g. "Games", "Goals", "Assists"), so they're captured from
# EVERY block that has them, not just one. Getting this wrong is what caused
# players who only appear on a single leaderboard (e.g. only "Shots Per
# Game") to lose their Games/ShotAttempts values in an earlier version of
# this script -- don't regress that.
global_map <- c(
  "Games" = "Games",
  "Goalie GP" = "GoalieGames",
  "Goals" = "TotalGoals",
  "Assists" = "TotalAssists",
  "Points" = "TotalPoints",
  "SoG" = "ShotsOnGoal",
  "ShAtt" = "ShotAttempts",
  "Saves" = "TotalSaves",
  "GA" = "GoalsAgainst",
  "Goalie Min. Plyd" = "GoalieMinutes",
  "Red Cards" = "RedCards",
  "Yellow Cards" = "YellowCards",
  "PS" = "PKGoals",
  "psatt" = "PKAttempts",
  "GWG" = "GameWinningGoals",
  "Shutouts" = "Shutouts",
  "GAA" = "GAA"
)

# ---- CATEGORY-SPECIFIC map ----------------------------------------------
# Only for ambiguous column names ("Per Game", "Pct.") whose meaning depends
# on which leaderboard page they're on.
category_map <- list(
  "Points Per Game"        = c(`Per Game` = "PointsPerGame"),
  "Penalty Kicks"          = c(`Pct.` = "PKPct"),
  "Goals Per Game"         = c(`Per Game` = "GoalsPerGame"),
  "Assists Per Game"       = c(`Per Game` = "AssistsPerGame"),
  "Save Pct"               = c(`Pct.` = "SavePct"),
  "Saves Per Game"         = c(`Per Game` = "SavesPerGame"),
  "Shot Accuracy"          = c(`Pct.` = "ShotAccuracyPct"),
  "Shots on Goal Per Game" = c(`Per Game` = "ShotsOnGoalPerGame"),
  "Shots Per Game"         = c(`Per Game` = "ShotsPerGame")
)

final_cols <- c("Name","Team","Cl","Ht","Pos","Games","GoalieGames",
  "TotalGoals","GoalsPerGame","TotalAssists","AssistsPerGame",
  "TotalPoints","PointsPerGame","GameWinningGoals",
  "ShotAttempts","ShotsPerGame","ShotsOnGoal","ShotsOnGoalPerGame",
  "ShotAccuracyPct","PKGoals","PKAttempts","PKPct",
  "YellowCards","RedCards",
  "TotalSaves","SavesPerGame","SavePct","Shutouts",
  "GoalieMinutes","GoalsAgainst","GAA")

clean_ncaa_individual_stats <- function(path) {
  raw <- readLines(path, warn = FALSE, encoding = "latin1")
  raw <- iconv(raw, from = "latin1", to = "UTF-8")

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

  # Merge all blocks into one row per (Name, Team)
  players <- list()
  for (b in blocks) {
    df <- b$data
    if (!("Name" %in% names(df)) || !("Team" %in% names(df))) next
    cat_specific <- category_map[[b$category]]

    for (r in seq_len(nrow(df))) {
      name <- str_trim(df$Name[r])
      team <- str_trim(df$Team[r])
      key <- paste(name, team, sep = "\u0001")  # unlikely-collision separator
      if (is.null(players[[key]])) players[[key]] <- list(Name = name, Team = team)

      # bio fields, keep first non-empty
      for (bio in c("Cl", "Ht", "Pos")) {
        if (bio %in% names(df) && (is.null(players[[key]][[bio]]) || players[[key]][[bio]] == "")) {
          players[[key]][[bio]] <- df[[bio]][r]
        }
      }

      # global columns -- fill from ANY block, first non-empty wins
      for (src in names(global_map)) {
        dest <- global_map[[src]]
        if (src %in% names(df) && (is.null(players[[key]][[dest]]) || players[[key]][[dest]] == "")) {
          players[[key]][[dest]] <- df[[src]][r]
        }
      }

      # category-specific ambiguous columns
      if (!is.null(cat_specific)) {
        for (src in names(cat_specific)) {
          dest <- cat_specific[[src]]
          if (src %in% names(df)) {
            players[[key]][[dest]] <- df[[src]][r]
          }
        }
      }
    }
  }

  out <- do.call(rbind, lapply(players, function(p) {
    vals <- sapply(final_cols, function(c) if (is.null(p[[c]])) NA else p[[c]])
    as.data.frame(t(vals), stringsAsFactors = FALSE)
  }))
  colnames(out) <- final_cols
  rownames(out) <- NULL

  # Red/Yellow card leaderboards list every non-zero player (no top-N
  # cutoff), so NA there really does mean zero. Every OTHER stat column is a
  # depth-limited leaderboard (top ~150-360), so NA there means "didn't
  # qualify," not zero -- do NOT fill those.
  out$YellowCards[is.na(out$YellowCards)] <- "0"
  out$RedCards[is.na(out$RedCards)] <- "0"

  numeric_cols <- setdiff(final_cols, c("Name", "Team", "Cl", "Ht", "Pos"))
  out[numeric_cols] <- lapply(out[numeric_cols], function(x) suppressWarnings(as.numeric(x)))

  out
}
