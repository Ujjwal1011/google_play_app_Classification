import gplay from "google-play-scraper";

gplay.list({
    category: gplay.category.FINANCE,
    num: 1000
})
.then(console.log, console.log);
