/************************************************************
 * Arabian Peninsula ultra-split version - rerun-safe
 * ESA WorldCover 2020 + Dynamic World 2020 mode
 *
 * Main fixes retained from the North America version:
 *   1. Supports rerunning only failed subtiles.
 *   2. Avoids ee.List.filter(ee.Filter.eq('class', code)) error.
 *   3. Handles empty Dynamic World image collections.
 *   4. Handles tiles with no oasis polygons.
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
// 0. Rerun control
// ==========================================================

/*
Arabian Peninsula grid:
  lon: 34 to 60
  lat: 12 to 40
  step: 2 degrees x 2 degrees

Total tiles:
  13 longitude columns x 14 latitude rows = 182 subtiles.

First full run:
  Keep the line below.

Rerun failed tiles only:
  Replace with a list, for example:
  var tilesToRun = [1, 2, 17, 45];
*/
var tilesToRun = ee.List.sequence(1, 182).getInfo();

print('Tiles selected:', tilesToRun);


// ==========================================================
// 1. Load Arabian Peninsula oasis polygons
// ==========================================================

var oasis = ee.FeatureCollection(
  'users/linjingwu08/oasis_arabian_peninsula_simplified10m'
);

var regionName = 'Arabian_Peninsula';
var parentTileName = 'Arabian_Peninsula_full';
var driveFolder = 'Arabian_Peninsula_LC_ESA_DW_2020';

print('Oasis asset:', 'users/linjingwu08/oasis_arabian_peninsula_simplified10m');
print('Number of oasis polygons:', oasis.size());
print('Oasis bounds:', oasis.geometry().bounds());


// ==========================================================
// 2. Harmonized class scheme
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
// 3. ESA WorldCover 2020 harmonization
// ==========================================================

var esaRaw = ee.ImageCollection('ESA/WorldCover/v100')
  .first()
  .select('Map');

var esaH = esaRaw.remap(
  [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
  [ 2,  2,  2,  1,  4,  5,  7,  6,  3,  3,   8]
).rename('class').toByte();


// ==========================================================
// 4. Dynamic World 2020 harmonization
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
// 5. Generate ultra-small tiles for Arabian Peninsula
// ==========================================================

/*
Oasis asset bounds checked locally:
  lon: 34.22038554576719 to 59.81653532055656
  lat: 12.610092533441994 to 38.287817054646446

The grid below adds a small margin:
  lon: 34 to 60
  lat: 12 to 40
*/

var lonStarts = [
  34, 36, 38, 40, 42, 44, 46,
  48, 50, 52, 54, 56, 58
];

var latStarts = [
  12, 14, 16, 18, 20, 22, 24,
  26, 28, 30, 32, 34, 36, 38
];

var lonStep = 2;
var latStep = 2;


// ==========================================================
// 6. Zero-output function
// ==========================================================

function makeZeroFeatures(productName, tileName) {
  var features = classCodes.map(function(code) {
    code = ee.Number(code);

    return ee.Feature(null, {
      Region: regionName,
      Region_type: 'Region_subtile',
      Parent_tile: parentTileName,
      Tile: tileName,
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

function calculateAreaByClass(image, productName, tileName, tileGeom, scale) {

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
   * Critical fix:
   * Do NOT use:
   *   groups.filter(ee.Filter.eq('class', code))
   *
   * ee.List.filter in GEE expects the field name 'item',
   * so filtering a list of dictionaries by 'class' can fail.
   *
   * Instead, convert grouped results to a dictionary:
   *   class code -> area sum
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
      Region_type: 'Region_subtile',
      Parent_tile: parentTileName,
      Tile: tileName,
      Product: productName,
      Class_code: code,
      Class_name: classInfo.get(key),
      Area_km2: areaKm2
    });
  });

  var statsFC = ee.FeatureCollection(features);
  var zeroFC = makeZeroFeatures(productName, tileName);

  return ee.FeatureCollection(
    ee.Algorithms.If(
      hasOasis,
      statsFC,
      zeroFC
    )
  );
}


// ==========================================================
// 8. Helper: tile number to geometry
// ==========================================================

function getTileInfo(tileNumber) {
  tileNumber = Number(tileNumber);

  var latIndex = Math.floor((tileNumber - 1) / lonStarts.length);
  var lonIndex = (tileNumber - 1) % lonStarts.length;

  var lon0 = lonStarts[lonIndex];
  var lat0 = latStarts[latIndex];

  var lon1 = lon0 + lonStep;
  var lat1 = lat0 + latStep;

  var tileName = 'AP_sub_' + tileNumber;

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
    tileInfo.tileName,
    tileInfo.tileGeom,
    10
  );

  var dwH = getDWHarmonized(tileInfo.tileGeom);

  var dwStats = calculateAreaByClass(
    dwH,
    'Dynamic_World_2020_mode',
    tileInfo.tileName,
    tileInfo.tileGeom,
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
