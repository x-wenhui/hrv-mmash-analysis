# Step 5 (optional): within-person coupling of HRV in the hour before each
# PANAS rating with the rated positive / negative affect.
#
# Input : derived/hrv_5min_state.csv, questionnaire.csv
# Output: derived/panas_models.rds, output/tables/panas_hrv.csv, output/tables/panas_models.txt,
#         output/figures/panas_within.png

suppressPackageStartupMessages({
  library(tidyverse)
  library(mgcv)
})

root <- here::here()
raw <- file.path(root, "data",
                 "multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0",
                 "MMASH", "DataPaper")
DAY1 <- as.POSIXct("2000-01-01", tz = "UTC")   # same reference date as Python
MIN_WINDOWS <- 6                                # >= 30 of the 60 min usable

# PANAS was rated at 10, 14, 18, 22 h on day 1 and 09 h on day 2.
rating_times <- tibble(
  timepoint = c("10", "14", "18", "22", "9+1"),
  rating_time = DAY1 + c(10, 14, 18, 22, 24 + 9) * 3600
)

panas <- map_dfr(1:22, \(u) {
  read_csv(file.path(raw, paste0("user_", u), "questionnaire.csv"),
           show_col_types = FALSE, name_repair = "unique_quiet") |>
    select(starts_with("panas")) |>
    mutate(user = u)
}) |>
  pivot_longer(starts_with("panas"),
               names_to = c("scale", "timepoint"),
               names_pattern = "panas_(pos|neg)_(.*)") |>
  pivot_wider(names_from = scale, values_from = value) |>
  left_join(rating_times, by = "timepoint")

hrv <- read_csv(file.path(root, "derived", "hrv_5min_state.csv"),
                show_col_types = FALSE) |>
  filter(usable) |>
  mutate(window_start = force_tz(window_start, "UTC"))

# HRV in the 60 min before each rating: windows that end at or before it.
pre <- panas |>
  left_join(hrv, by = "user", relationship = "many-to-many") |>
  filter(window_start >= rating_time - 3600,
         window_start + 300 <= rating_time) |>
  group_by(user, timepoint) |>
  summarise(n_windows = n(),
            ln_rmssd = mean(ln_rmssd), mean_hr = mean(mean_hr),
            .groups = "drop")

d <- panas |>
  left_join(pre, by = c("user", "timepoint")) |>
  mutate(n_windows = replace_na(n_windows, 0L),
         ok = n_windows >= MIN_WINDOWS) |>
  arrange(user, rating_time)
write_csv(d, file.path(root, "output", "tables", "panas_hrv.csv"))

# Person-mean centring separates the within-person question ("when this
# person's HRV is higher than usual, is their affect different?") from the
# between-person one ("do people with higher HRV report different affect?").
m_dat <- d |>
  filter(ok, !is.na(pos), !is.na(neg)) |>   # user 13 lacks the 14 h rating
  group_by(user) |>
  filter(n() >= 2) |>
  mutate(hrv_between = mean(ln_rmssd),
         hrv_within = ln_rmssd - hrv_between) |>
  ungroup() |>
  mutate(user = factor(user), timepoint = factor(timepoint, rating_times$timepoint))

# timepoint as a fixed effect: affect and HRV both change across the day, so
# without it any shared time-of-day trend would look like coupling.
fit <- \(y) gam(reformulate(c("hrv_within", "hrv_between", "timepoint",
                              "s(user, bs = 're')"), y),
                data = m_dat, method = "REML")
m_pos <- fit("pos")
m_neg <- fit("neg")
saveRDS(list(pos = m_pos, neg = m_neg, data = m_dat),
        file.path(root, "derived", "panas_models.rds"))

sink(file.path(root, "output", "tables", "panas_models.txt"))
cat("Ratings with >=", MIN_WINDOWS, "usable windows in the preceding hour:",
    sum(d$ok), "of", nrow(d), "\n")
print(count(d, timepoint, ok))
cat("\nModel data:", nrow(m_dat), "ratings from", nlevels(m_dat$user), "participants\n\n")
cat("===== Positive affect =====\n"); print(summary(m_pos))
cat("\n===== Negative affect =====\n"); print(summary(m_neg))
sink()

p <- m_dat |>
  group_by(user) |>
  mutate(pos_within = pos - mean(pos), neg_within = neg - mean(neg)) |>
  ungroup() |>
  pivot_longer(c(pos_within, neg_within), names_to = "scale", values_to = "affect") |>
  mutate(scale = recode(scale, pos_within = "Positive affect", neg_within = "Negative affect")) |>
  ggplot(aes(hrv_within, affect)) +
  geom_hline(yintercept = 0, colour = "grey70") +
  geom_vline(xintercept = 0, colour = "grey70") +
  geom_point(alpha = 0.6) +
  geom_smooth(method = "lm", formula = y ~ x, colour = "steelblue4") +
  facet_wrap(~scale) +
  labs(x = "lnRMSSD in preceding hour (deviation from own mean)",
       y = "PANAS (deviation from own mean)",
       caption = "Each point = one rating. Simple fit for display; inference from the mixed model.") +
  theme_minimal(base_size = 12)
ggsave(file.path(root, "output", "figures", "panas_within.png"), p,
       width = 8, height = 4, dpi = 150)

for (m in list(m_pos, m_neg)) print(summary(m)$p.table)
cat("n ratings:", nrow(m_dat), " participants:", nlevels(m_dat$user), "\n")
