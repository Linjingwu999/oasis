/************************************************************
 * Global ultra-split version - skipping North America
 * ESA WorldCover 2020 + Dynamic World 2020 mode
 *
 * Input oasis asset:
 *   users/linjingwu08/oasis_global_simplified10m
 *
 * Main design:
 *   1. Uses 2 degree x 2 degree tiles.
 *   2. Defaults to non-empty oasis tiles outside North America only.
 *   3. Supports batch submission to avoid freezing the GEE Code Editor.
 *   4. Supports rerunning failed tile IDs only.
 *   5. Handles empty Dynamic World image collections.
 *   6. Handles tiles with no oasis polygons.
 *
 * North America is skipped because that result has already been generated.
 *
 * Output:
 *   One CSV per subtile.
 *   Each CSV contains ESA and Dynamic World area statistics.
 *
 * Important:
 *   Do not average percentages across tiles.
 *   Merge CSVs locally by summing Area_km2, then recalculate Percent.
 ************************************************************/


// ==========================================================
// 0. Batch and rerun control
// ==========================================================

/*
Global non-North-America active tiles:
  Grid bounds: lon -82 to 146, lat -36 to 52
  Tile size: 2 degrees x 2 degrees
  Full grid size: 114 columns x 44 rows = 5016 possible tiles
  Default active tiles: 565 tiles that intersect global oasis polygons
  North America exclusion: local global shapefile ContinentI == 'NA'

Recommended use:
  First run batch 0-99, then 100-199, 200-299, 300-399, 400-499, 500-564.

If the Code Editor and task panel are responsive, you may set:
  var batchStartIndex = 0;
  var batchEndIndex = 564;

To rerun failed tiles only:
  Put failed tile IDs in failedTileIdsToRun, for example:
  var failedTileIdsToRun = [3497, 3498, 3609];
*/

var batchStartIndex = 0;
var batchEndIndex = 99;

var failedTileIdsToRun = [];


// ==========================================================
// 1. Load global oasis polygons
// ==========================================================

var oasisAsset = 'users/linjingwu08/oasis_global_simplified10m';

var oasis = ee.FeatureCollection(oasisAsset);

var regionName = 'Global_without_North_America';
var parentTileName = 'Global_2deg_nonempty_skip_NA';
var driveFolder = 'Global_LC_ESA_DW_2020_skip_NA';

print('Oasis asset:', oasisAsset);
print('Number of global oasis polygons:', oasis.size());
print('North America is skipped by default.');


// ==========================================================
// 2. Tile grid
// ==========================================================

var lonStart = -82;
var latStart = -36;
var lonStep = 2;
var latStep = 2;
var lonColumns = 114;

/*
These row/column ranges were generated from the local
oasis_global_simplified10m shapefile on 2026-05-28.
They keep only tiles that intersect oasis polygons after excluding
features whose ContinentI field is 'NA'.
*/
var activeTileRowColRanges = [
  {row: 0, ranges: [[6, 6]]},
  {row: 1, ranges: [[6, 7]]},
  {row: 2, ranges: [[5, 6], [49, 50], [110, 111]]},
  {row: 3, ranges: [[5, 7], [49, 49], [108, 112]]},
  {row: 4, ranges: [[5, 8], [48, 48], [108, 113]]},
  {row: 5, ranges: [[6, 8], [97, 97], [107, 108], [110, 112]]},
  {row: 6, ranges: [[5, 6], [8, 8], [48, 48], [98, 98], [108, 111]]},
  {row: 7, ranges: [[6, 7], [47, 48], [98, 100], [109, 110]]},
  {row: 8, ranges: [[5, 7], [47, 47], [100, 102]]},
  {row: 9, ranges: [[4, 7]]},
  {row: 10, ranges: [[2, 4], [46, 47]]},
  {row: 11, ranges: [[2, 3], [47, 47]]},
  {row: 12, ranges: [[1, 2]]},
  {row: 13, ranges: [[1, 1]]},
  {row: 14, ranges: [[0, 1]]},
  {row: 15, ranges: [[0, 1]]},
  {row: 17, ranges: [[60, 61]]},
  {row: 18, ranges: [[58, 61]]},
  {row: 19, ranges: [[58, 59], [61, 62]]},
  {row: 20, ranges: [[61, 63]]},
  {row: 21, ranges: [[62, 63]]},
  {row: 23, ranges: [[45, 46], [61, 66]]},
  {row: 24, ranges: [[37, 38], [41, 42], [45, 48], [57, 58], [62, 65]]},
  {row: 25, ranges: [[29, 29], [32, 41], [45, 45], [47, 48], [57, 67]]},
  {row: 26, ranges: [[28, 29], [32, 37], [39, 41], [44, 44], [56, 60], [62, 65], [67, 68]]},
  {row: 27, ranges: [[32, 36], [44, 44], [46, 47], [56, 60], [63, 63], [67, 69]]},
  {row: 28, ranges: [[32, 35], [47, 47], [56, 56], [59, 59], [63, 64], [68, 70]]},
  {row: 29, ranges: [[32, 33], [54, 59], [63, 70]]},
  {row: 30, ranges: [[33, 33], [35, 35], [45, 48], [51, 52], [55, 58], [62, 75]]},
  {row: 31, ranges: [[33, 35], [40, 42], [45, 45], [47, 49], [54, 76]]},
  {row: 32, ranges: [[34, 36], [38, 41], [44, 45], [48, 51], [53, 71], [74, 77]]},
  {row: 33, ranges: [[36, 40], [42, 78]]},
  {row: 34, ranges: [[36, 48], [50, 53], [58, 59], [62, 78]]},
  {row: 35, ranges: [[39, 46], [59, 73], [75, 75], [89, 89]]},
  {row: 36, ranges: [[45, 46], [59, 90], [92, 94]]},
  {row: 37, ranges: [[60, 65], [68, 80], [82, 94]]},
  {row: 38, ranges: [[62, 63], [70, 85], [87, 91], [94, 96]]},
  {row: 39, ranges: [[70, 72], [74, 88], [91, 91]]},
  {row: 40, ranges: [[70, 86], [89, 91]]},
  {row: 41, ranges: [[71, 72], [79, 89]]},
  {row: 42, ranges: [[83, 84], [86, 88]]},
  {row: 43, ranges: [[86, 88]]}
];

function expandActiveTileIds(rowColRanges) {
  var tileIds = [];

  rowColRanges.forEach(function(item) {
    item.ranges.forEach(function(range) {
      for (var col = range[0]; col <= range[1]; col++) {
        tileIds.push(item.row * lonColumns + col + 1);
      }
    });
  });

  return tileIds;
}

var activeTileIds = expandActiveTileIds(activeTileRowColRanges);
var tilesToRun = failedTileIdsToRun.length > 0
  ? failedTileIdsToRun
  : activeTileIds.slice(batchStartIndex, batchEndIndex + 1);

print('Total active non-North-America oasis tiles:', activeTileIds.length);
print('Batch start index:', batchStartIndex);
print('Batch end index:', batchEndIndex);
print('Tiles selected for this run:', tilesToRun);


// ==========================================================
// 3. Harmonized class scheme
// ==========================================================

var classInfo = ee.Dictionary({
  '1': 'Cropland',
  '2': 'Tree_shrub_grass_vegetation',
  '3': 'Wetland_mangrove_flooded_vegetation',
  '4': 'Built_up',
  '5': 'Bare_or_sparse_vegetation',
  '6': 'Water',
  '7': 'Snow_ice',
  '8': 'Other'
});

var classCodes = ee.List([1, 2, 3, 4, 5, 6, 7, 8]);


// ==========================================================
// 4. ESA WorldCover 2020 harmonization
// ==========================================================

var esaRaw = ee.ImageCollection('ESA/WorldCover/v100')
  .first()
  .select('Map');

var esaH = esaRaw.remap(
  [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
  [ 2,  2,  2,  1,  4,  5,  7,  6,  3,  3,   8]
).rename('class').toByte();


// ==========================================================
// 5. Dynamic World 2020 harmonization
// ==========================================================

var dwCollection = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
  .filterDate('2020-01-01', '2021-01-01')
  .select('label');

function getDWHarmonized(tileGeom) {
  var dwTile = dwCollection.filterBounds(tileGeom);
  var n = dwTile.size();

  var dwLabel = ee.Image(
    ee.Algorithms.If(
      n.gt(0),
      dwTile.mode().rename('label'),
      ee.Image(0).rename('label').updateMask(ee.Image(0))
    )
  );

  var dwH = dwLabel.remap(
    [0, 1, 2, 3, 4, 5, 6, 7, 8],
    [6, 2, 2, 3, 1, 2, 4, 5, 7]
  ).rename('class').toByte();

  return dwH;
}


// ==========================================================
// 6. Zero-output function
// ==========================================================

function makeZeroFeatures(productName, tileInfo) {
  var features = classCodes.map(function(code) {
    code = ee.Number(code);

    return ee.Feature(null, {
      Region: regionName,
      Region_type: 'Global_subtile',
      Parent_tile: parentTileName,
      Tile: tileInfo.tileName,
      Tile_id: tileInfo.tileNumber,
      Tile_lon0: tileInfo.lon0,
      Tile_lat0: tileInfo.lat0,
      Tile_lon1: tileInfo.lon1,
      Tile_lat1: tileInfo.lat1,
      Product: productName,
      Class_code: code,
      Class_name: classInfo.get(code.format()),
      Area_km2: 0
    });
  });

  return ee.FeatureCollection(features);
}


// ==========================================================
// 7. Area statistics function
// ==========================================================

function calculateAreaByClass(image, productName, tileInfo, scale) {

  var tileGeom = tileInfo.tileGeom;
  var tileOasis = oasis.filterBounds(tileGeom);
  var hasOasis = tileOasis.size().gt(0);

  var oasisMask = ee.Image(0)
    .byte()
    .paint({
      featureCollection: tileOasis,
      color: 1
    })
    .clip(tileGeom)
    .selfMask();

  var maskedClass = image
    .updateMask(oasisMask)
    .clip(tileGeom);

  var areaImage = ee.Image.pixelArea()
    .divide(1e6)
    .rename('area_km2')
    .addBands(maskedClass.rename('class'));

  var result = areaImage.reduceRegion({
    reducer: ee.Reducer.sum().group({
      groupField: 1,
      groupName: 'class'
    }),
    geometry: tileGeom,
    scale: scale,
    maxPixels: 1e13,
    tileScale: 16,
    bestEffort: true
  });

  var groups = ee.List(
    ee.Algorithms.If(
      result.contains('groups'),
      result.get('groups'),
      ee.List([])
    )
  );

  /*
   * Do not use groups.filter(ee.Filter.eq('class', code)).
   * ee.List.filter expects the field name 'item', so that pattern can fail.
   * Convert grouped results to a dictionary: class code -> area sum.
   */

  var groupKeys = groups.map(function(g) {
    g = ee.Dictionary(g);
    return ee.Number(g.get('class')).format();
  });

  var groupValues = groups.map(function(g) {
    g = ee.Dictionary(g);
    return ee.Number(g.get('sum'));
  });

  var areaDict = ee.Dictionary.fromLists(groupKeys, groupValues);

  var features = classCodes.map(function(code) {
    code = ee.Number(code);
    var key = code.format();

    var areaKm2 = ee.Number(
      ee.Algorithms.If(
        areaDict.contains(key),
        areaDict.get(key),
        0
      )
    );

    return ee.Feature(null, {
      Region: regionName,
      Region_type: 'Global_subtile',
      Parent_tile: parentTileName,
      Tile: tileInfo.tileName,
      Tile_id: tileInfo.tileNumber,
      Tile_lon0: tileInfo.lon0,
      Tile_lat0: tileInfo.lat0,
      Tile_lon1: tileInfo.lon1,
      Tile_lat1: tileInfo.lat1,
      Product: productName,
      Class_code: code,
      Class_name: classInfo.get(key),
      Area_km2: areaKm2
    });
  });

  var statsFC = ee.FeatureCollection(features);
  var zeroFC = makeZeroFeatures(productName, tileInfo);

  return ee.FeatureCollection(
    ee.Algorithms.If(
      hasOasis,
      statsFC,
      zeroFC
    )
  );
}


// ==========================================================
// 8. Tile helpers
// ==========================================================

function getTileInfo(tileNumber) {
  tileNumber = Number(tileNumber);

  var rowIndex = Math.floor((tileNumber - 1) / lonColumns);
  var colIndex = (tileNumber - 1) % lonColumns;

  var lon0 = lonStart + colIndex * lonStep;
  var lat0 = latStart + rowIndex * latStep;

  var lon1 = lon0 + lonStep;
  var lat1 = lat0 + latStep;

  var tileName = 'GLB_noNA_sub_' + tileNumber;

  var tileGeom = ee.Geometry.Rectangle(
    [lon0, lat0, lon1, lat1],
    null,
    false
  );

  return {
    tileNumber: tileNumber,
    tileName: tileName,
    lon0: lon0,
    lat0: lat0,
    lon1: lon1,
    lat1: lat1,
    tileGeom: tileGeom
  };
}


// ==========================================================
// 9. Export selected subtiles
// ==========================================================

tilesToRun.forEach(function(tileNumber) {

  var tileInfo = getTileInfo(tileNumber);

  print(
    'Submitting tile:',
    tileInfo.tileName,
    'lon:',
    tileInfo.lon0,
    tileInfo.lon1,
    'lat:',
    tileInfo.lat0,
    tileInfo.lat1
  );

  var esaStats = calculateAreaByClass(
    esaH,
    'ESA_WorldCover_2020',
    tileInfo,
    10
  );

  var dwH = getDWHarmonized(tileInfo.tileGeom);

  var dwStats = calculateAreaByClass(
    dwH,
    'Dynamic_World_2020_mode',
    tileInfo,
    10
  );

  var tileStats = esaStats.merge(dwStats);

  Export.table.toDrive({
    collection: tileStats,
    description: 'LC_' + tileInfo.tileName + '_ESA_DW_2020',
    folder: driveFolder,
    fileNamePrefix: 'LC_' + tileInfo.tileName + '_ESA_DW_2020',
    fileFormat: 'CSV'
  });

});
