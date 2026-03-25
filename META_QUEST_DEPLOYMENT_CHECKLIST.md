# Meta Quest Deployment Checklist

Repository:
`https://github.com/hudsonclavin-cloud/Bureaucracy.git`

Expected GitHub Pages URL:
`https://hudsonclavin-cloud.github.io/Bureaucracy/`

## Publish

1. Push the latest `main` branch to GitHub.
2. In GitHub repository settings, confirm **Pages** is serving from:
   - Branch: `main`
   - Folder: `/ (root)`
3. Wait for the Pages deployment to finish before testing in-headset.

## WebXR Requirements

1. Test from the published `https` URL only.
2. Open the site in **Meta Quest Browser**.
3. Confirm `Enter VR` appears only on Quest / WebXR-capable browsers.

## Cache Busting

When changing VR runtime files, bump the module query string versions in:
- `index.html`
- `js/ui.js`

Files that should stay cache-busted together:
- `js/ui.js`
- `js/graph.js`
- `js/vrMode.js`
- `js/vrControls.js`
- `js/vrHud.js`
- `js/vrConfig.js`

## Quest Smoke Test

1. Load the published site in Quest Browser.
2. Wait for graph data to finish loading.
3. Click `Enter VR`.
4. Verify:
   - immersive session starts
   - controller rays are visible
   - trigger selects nodes
   - squeeze focuses selected node
   - `A/X` expands
   - `B/Y` collapses or traces
   - stick press recenters
   - left stick moves
   - right stick snap-turns / vertical-moves

## Performance Checks

1. Initial Constitution-centered load is readable.
2. Medium branch expansion stays responsive.
3. Dense branch exploration still clusters correctly.
4. `Expand All` in VR shows the limited-depth warning instead of trying a full global expansion.

## If Quest Shows Old Code

1. Hard refresh Quest Browser.
2. Restart Quest Browser.
3. Confirm cache-busting query strings changed in the deployed HTML.
