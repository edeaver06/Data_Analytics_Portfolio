# Render the static flexdashboard to app/dashboard.html (self-contained, no server needed).
rmarkdown::render("app/dashboard.Rmd", output_file = "dashboard.html", knit_root_dir = getwd(), quiet = TRUE)
