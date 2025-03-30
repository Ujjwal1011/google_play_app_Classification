import gplay from "google-play-scraper";
import fs from "fs";

async function fetchApps(searchQueries, numPerQuery, totalAppsNeeded, outputFile) {
    let allApps = new Map();
    let fetchedCount = 0;

    // Await the result of gplay.suggest
    searchQueries = await gplay.suggest({ term: searchQueries[0] });
    console.log();
    console.log("Search queries:", searchQueries);
    for (const query of searchQueries) {
        if (fetchedCount >= totalAppsNeeded) break;
        try {
            const apps = await gplay.search({ term: query, num: numPerQuery ,country:"in" });
            for (const app of apps) {
                if (!allApps.has(app.appId) && fetchedCount < totalAppsNeeded) {
                    allApps.set(app.appId, app);
                    fetchedCount++;
                }
                if (fetchedCount >= totalAppsNeeded) break;
            }
        } catch (error) {
            console.error(`Error fetching for query "${query}":`, error);
        }
    }

    const data = Array.from(allApps.values()).slice(0, totalAppsNeeded);

    if (outputFile) {
        try {
            fs.writeFileSync(outputFile, JSON.stringify(data, null, 2));
            console.log(`Saved ${data.length} apps to ${outputFile}`);
        } catch (error) {
            console.error(`Error writing to file "${outputFile}":`, error);
        }
    }


}

// Get command-line arguments
const searchQueriesArg = process.argv.slice(2)[0];
const numPerQueryArg = process.argv.slice(3)[0];
const totalAppsNeededArg = process.argv.slice(4)[0];
const outputFileArg = process.argv.slice(5)[0];

if (!searchQueriesArg || !numPerQueryArg || !totalAppsNeededArg) {
    console.error("Usage: node fetch_from_gplay.js '[{\"term\": \"search1\"}, {\"term\": \"search2\"}]' <num_per_query> <total_apps_needed> [output_file]");
    process.exit(1);
}

try {
    const searchQueries = JSON.parse(searchQueriesArg);
    const numPerQuery = parseInt(numPerQueryArg, 10);
    const totalAppsNeeded = parseInt(totalAppsNeededArg, 10);

    await fetchApps(searchQueries, numPerQuery, totalAppsNeeded, outputFileArg);
} catch (error) {
    console.error("Error processing arguments or fetching data:", error);
    process.exit(1);
}