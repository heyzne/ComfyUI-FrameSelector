# Project Memory

## Default Deselect Feature (2026-09-30)

Modified `web/js/frame_selector.js` to remove auto-selection default:

**Before**: All images were auto-selected when the dialog opened.
**After**: All images start unselected (dimmed with 35% opacity). User must click to toggle selection.

### Changes made:
1. **CSS** (line 17-18):
   - Added `opacity: 0.35` to all images (dimmed by default)
   - Added `.fs-selected` class with blue border, `opacity: 1`

2. **JavaScript** (lines 135-140):
   - Removed: `img.classList.add("fs-sel"); selected.add(i);`
   - Added: `img.classList.add("fs-selected")`, `img.setAttribute("data-index", i)`, `img.style.opacity = "0.7"`

3. **Selection logic** (lines 105-114):
   - `fs-all` selects all images
   - `fs-none` deselects all images

4. **Click handler** (lines 141-145):
   - Toggles between selected (opacity: 1) and unselected (opacity: 0.35)

### Behavior:
- All thumbnail images appear dimmed (35% opacity) on dialog-open
- User clicks image → it lights up (100% opacity) with blue border
- The "Confirm" button is disabled until at least one image is selected
- "Select All" selects all images at once
- "Deselect All" deselects all images

### Why this matters:
Prevents accidentally passing all frames through the pipeline. Now the user must explicitly choose which frames they want, reducing unexpected outputs in long video sequences.
