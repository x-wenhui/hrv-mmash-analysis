# Step 4: 24-h diurnal HRV profile with a GAMM (mgcv), plus an exploratory
# MEQ (chronotype) x clock-time interaction.
#
# Input : derived/hrv_5min_state.csv (Python steps 1-3), questionnaire.csv
# Output: derived/gamm_models.rds, output/tables/gamm_summary.txt, output/figures/*.png

suppressPackageStartupMessages({
  library(tidyverse)
  library(mgcv)
})

root <- here::here()
raw <- file.path(root, "data",
                 "multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0",
                 "MMASH", "DataPaper")

# ---- data -------------------------------------------------------------------
meq <- map_dfr(1:22, \(u) {
  read_csv(file.path(raw, paste0("user_", u), "questionnaire.csv"),
           show_col_types = FALSE, name_repair = "unique_quiet") |>
    transmute(user = u, MEQ = as.numeric(MEQ))
})

hrv <- read_csv(file.path(root, "derived", "hrv_5min_state.csv"),
                show_col_types = FALSE) |>
  filter(usable) |>
  left_join(meq, by = "user") |>
  mutate(
    user = factor(user),
    clock = clock_hour + 2.5 / 60,        # window midpoint, hours 0-24
    sleep = factor(state == "sleep", c(FALSE, TRUE), c("not asleep", "asleep"))
  ) |>
  arrange(user, window_start) |>
  # AR(1) restarts for each participant and after any skipped window
  mutate(ar_start = user != lag(user, default = first(user)) |
           as.numeric(difftime(window_start, lag(window_start), units = "mins")) != 5,
         ar_start = replace_na(ar_start, TRUE))

# Cyclic smooth: 23:59 and 00:00 must join up.
knots <- list(clock = c(0, 24))

# ---- model 1: diurnal profile ----------------------------------------------
# lnRMSSD ~ smooth of clock time + participant random intercept.
# First fit without AR to estimate the lag-1 residual autocorrelation of
# consecutive 5-min windows, then refit with an AR(1) error (rho).
fit_profile <- function(y, rho = 0) {
  bam(reformulate(c("s(clock, bs = 'cc', k = 16)", "s(user, bs = 're')"), y),
      data = hrv, knots = knots, method = "fREML",
      rho = rho, AR.start = hrv$ar_start)
}
m0 <- fit_profile("ln_rmssd")
rho <- acf(resid(m0), plot = FALSE)$acf[2]
m_rmssd <- fit_profile("ln_rmssd", rho)
m_hr    <- fit_profile("mean_hr", acf(resid(fit_profile("mean_hr")), plot = FALSE)$acf[2])

# Sensitivity: participant-specific deviations from the common curve
# (factor-smooth interaction) instead of a random intercept only.
m_fs <- bam(ln_rmssd ~ s(clock, bs = "cc", k = 16) +
              s(clock, user, bs = "fs", xt = list(bs = "cc"), k = 8, m = 1),
            data = hrv, knots = knots, method = "fREML",
            rho = rho, AR.start = hrv$ar_start)

# ---- model 2: exploratory MEQ interaction ----------------------------------
# Does the shape of the 24-h profile differ with chronotype (MEQ score)?
# ti() isolates the interaction from the two main effects. MEQ is a
# between-person variable, so participant-specific curves (fs) must be in
# the model; with a random intercept only, any individual difference in curve
# shape would be (wrongly) credited to MEQ and the p-value would be inflated.
m_meq <- bam(ln_rmssd ~ s(clock, bs = "cc", k = 16) + s(MEQ, k = 3) +
               ti(clock, MEQ, bs = c("cc", "tp"), k = c(10, 3)) +
               s(clock, user, bs = "fs", xt = list(bs = "cc"), k = 8, m = 1),
             data = hrv, knots = knots, method = "fREML",
             rho = rho, AR.start = hrv$ar_start)

# ---- save ---------------------------------------------------------------------
dir.create(file.path(root, "output", "figures"), recursive = TRUE, showWarnings = FALSE)
saveRDS(list(rmssd = m_rmssd, hr = m_hr, fs = m_fs, meq = m_meq, rho = rho),
        file.path(root, "derived", "gamm_models.rds"))

sink(file.path(root, "output", "tables", "gamm_summary.txt"))
cat("Windows:", nrow(hrv), " Participants:", nlevels(hrv$user),
    " AR(1) rho (lnRMSSD):", round(rho, 3), "\n\n")
for (nm in c("m_rmssd", "m_hr", "m_fs", "m_meq")) {
  cat("=====", nm, "=====\n"); print(summary(get(nm))); cat("\n")
}
sink()

# ---- figures --------------------------------------------------------------------
grid <- tibble(clock = seq(0, 24, by = 0.1), user = levels(hrv$user)[1])
pred_curve <- function(m, grid) {
  p <- predict(m, grid, se.fit = TRUE, exclude = c("s(user)", "s(clock,user)"))
  mutate(grid, fit = p$fit, lo = fit - 1.96 * p$se.fit, hi = fit + 1.96 * p$se.fit)
}
sleep_band <- read_csv(file.path(root, "derived", "sleep_periods.csv"),
                       show_col_types = FALSE) |>
  summarise(on = median(hour(onset) + minute(onset) / 60 - 24 * (hour(onset) > 12)),
            off = median(hour(out_bed) + minute(out_bed) / 60))
x_axis <- scale_x_continuous("Clock time (h)", breaks = seq(0, 24, 3), limits = c(0, 24))

plot_profile <- function(m, y, ylab) {
  ggplot(pred_curve(m, grid), aes(clock, fit)) +
    annotate("rect", xmin = max(0, sleep_band$on), xmax = sleep_band$off,
             ymin = -Inf, ymax = Inf, alpha = 0.12) +
    geom_point(data = hrv, aes(y = .data[[y]]), alpha = 0.04, size = 0.4) +
    geom_ribbon(aes(ymin = lo, ymax = hi), alpha = 0.3, fill = "steelblue") +
    geom_line(colour = "steelblue4", linewidth = 1) +
    x_axis + labs(y = ylab,
                  caption = "Grey band: median actigraphy sleep period. Points: 5-min windows.") +
    theme_minimal(base_size = 12)
}
ggsave(file.path(root, "output", "figures", "gamm_lnrmssd.png"),
       plot_profile(m_rmssd, "ln_rmssd", "lnRMSSD (ln ms)"), width = 7, height = 4, dpi = 150)
ggsave(file.path(root, "output", "figures", "gamm_hr.png"),
       plot_profile(m_hr, "mean_hr", "Mean heart rate (bpm)"), width = 7, height = 4, dpi = 150)

meq_lv <- quantile(meq$MEQ, c(0.1, 0.5, 0.9)) |> round()
meq_grid <- expand_grid(clock = seq(0, 24, by = 0.1), MEQ = meq_lv) |>
  mutate(user = levels(hrv$user)[1])
p_meq <- pred_curve(m_meq, meq_grid) |>
  mutate(MEQ = factor(MEQ, labels = paste0("MEQ = ", meq_lv, c(" (10th pct)", " (median)", " (90th pct)")))) |>
  ggplot(aes(clock, fit, colour = MEQ, fill = MEQ)) +
  geom_ribbon(aes(ymin = lo, ymax = hi), alpha = 0.15, colour = NA) +
  geom_line(linewidth = 1) + x_axis +
  labs(y = "lnRMSSD (ln ms)", colour = NULL, fill = NULL,
       caption = "Exploratory: n = 22, higher MEQ = more morning-type.") +
  theme_minimal(base_size = 12) + theme(legend.position = "bottom")
ggsave(file.path(root, "output", "figures", "gamm_meq.png"), p_meq, width = 7, height = 4.5, dpi = 150)

cat("Done. rho =", round(rho, 3), "\n")
print(AIC(m_rmssd, m_fs))
print(summary(m_meq)$s.table)
