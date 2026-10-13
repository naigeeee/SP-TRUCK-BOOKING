// ============================================================
// SP PH Truck Booking — Google Sheets Auto-Sync
// ============================================================
// SETUP:
// 1. Open Google Sheets → Extensions → Apps Script
// 2. Paste this entire script into Code.gs (replace what is there)
// 3. Set BACKEND_URL below to your deployed backend URL
// 4. Run setupSheets() once to create all tabs (re-run it after updating this
//    script to add the new tabs: Foul Trip Approval, Trip Utilisation Review and
//    Capacity Conversion)
// 5. Run installTrigger() once to enable hourly auto-sync
//
// Each tab mirrors the matching page in the app: the backend /api/sync/* endpoints
// return the same rows the page shows, and the column headers below follow the
// page's table. Headers, column formats and download links are refreshed on every
// sync. Download links open the app, so you need to be signed in to it.
// ============================================================

var BACKEND_URL = "https://sp-truck-booking--dev.ninjavan.apps.substrait.build";

var SECTIONS = [
  { key: "masterlist",          sheet: "Masterlist",               endpoint: "/api/sync/masterlist" },
  { key: "fleet",               sheet: "Fleet",                    endpoint: "/api/sync/fleet" },
  { key: "rates",               sheet: "Rate Management",          endpoint: "/api/sync/rates" },
  { key: "evaluation",          sheet: "Vendor Speed Performance", endpoint: "/api/sync/evaluation" },
  { key: "cost",                sheet: "Cost Analysis",            endpoint: "/api/sync/cost" },
  { key: "foul-trips",          sheet: "Foul Trip Approval",       endpoint: "/api/sync/foul-trips" },
  { key: "trip-utilisation",    sheet: "Trip Utilisation Review",  endpoint: "/api/sync/trip-utilisation" },
  { key: "ports",               sheet: "Ports",                    endpoint: "/api/sync/ports" },
  { key: "accounts",            sheet: "Accounts",                 endpoint: "/api/sync/accounts" },
  { key: "departments",         sheet: "Departments",              endpoint: "/api/sync/departments" },
  { key: "packaging",           sheet: "Packaging",                endpoint: "/api/sync/packaging" },
  { key: "statuses",            sheet: "Statuses",                 endpoint: "/api/sync/statuses" },
  { key: "truck-types",         sheet: "Truck Types",              endpoint: "/api/sync/truck-types" },
  { key: "vendors",             sheet: "Vendors",                  endpoint: "/api/sync/vendors" },
  { key: "capacity-conversion", sheet: "Capacity Conversion",      endpoint: "/api/sync/capacity-conversion" }
];

// Columns per tab: [header, field in the /api/sync/* response, type, link field].
// Types set the cell format on every sync, so a value is never mis-read by Sheets:
//   (none) text - kept exactly as sent (e.g. Trip ID 11E-00087 stays text, not a number)
//   int / num / money / pct - numbers      date / datetime - dates
//   link  - text with a download link (link field = path in the app)
//   files - list of attachments, each name linked to its download
var FIELDS = {
  "Masterlist": [
    ["Request #", "request_number"],
    ["Requestor Name", "requestor_name"],
    ["Requestor Email", "requestor_email"],
    ["Manifest", "manifest_status", "link", "manifest_url"],
    ["Pickup Scan Manifest", "pickup_scan_status", "link", "pickup_scan_url"],
    ["Unloading Scan Manifest", "unload_scan_status", "link", "unload_scan_url"],
    ["Status", "status_name"],
    ["Account", "account_name"],
    ["Department", "department_name"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["International MAWB", "international_mawb"],
    ["Domestic MAWB", "domestic_mawb"],
    ["Truck Type", "truck_type_name"],
    ["Truck Plate #", "plate_number"],
    ["Packaging", "packaging_type_name"],
    ["Initial Qty", "initial_qty", "num"],
    ["Revised Qty", "revised_qty_out", "num"],
    ["Vendor", "vendor_name"],
    ["Final Call Datetime", "final_call_datetime", "datetime"],
    ["Trip ID", "trip_id"],
    ["Driver", "driver_username"],
    ["Driver Name", "driver_name"],
    ["Driver Phone", "driver_phone"],
    ["Drop #", "drop_sequence", "int"],
    ["Distance (KM)", "distance_km", "num"],
    ["Booking Date", "booking_date", "date"],
    ["Initial Call datetime (TBC)", "call_datetime", "datetime"],
    ["Customs Cleared", "customs_cleared_datetime", "datetime"],
    ["Instructions", "special_instructions"],
    ["Arrived Pickup", "arrived_pickup_datetime", "datetime"],
    ["Late Reason", "late_reason"],
    ["Start Loading", "start_loading_datetime", "datetime"],
    ["End Loading", "end_loading_datetime", "datetime"],
    ["Arrived Destination", "arrived_dest_datetime", "datetime"],
    ["Start Unloading", "start_unloading_datetime", "datetime"],
    ["End Unloading", "end_unloading_datetime", "datetime"],
    ["Delivered Date", "delivered_date", "date"],
    ["Foul Trip Reason", "foul_trip_reason"],
    ["Foul Trip Date", "foul_trip_date", "date"],
    ["Foul Trip Count Confirmation", "foul_trip_count", "int"],
    ["Foul Trip Approval", "foul_trip_approved"],
    ["Cancellation Date", "cancellation_date", "date"],
    ["Consol", "consolidated"],
    ["Attachments", "attachments", "files"],
    ["Updated By", "updated_by_name"],
    ["Updated By Email", "updated_by_email"],
    ["Updated At", "updated_at", "datetime"],
    ["Created At", "created_at", "datetime"]
  ],
  "Fleet": [
    ["Plate #", "plate_number"],
    ["Truck Type", "truck_type_name"],
    ["Vendor", "vendor_name"],
    ["Driver Name", "driver_name"],
    ["Driver Phone", "driver_phone"],
    ["Helper Name", "helper_name"],
    ["Status", "status"],
    ["Capacity", "capacity", "num"],
    ["Is Active", "is_active"],
    ["Current Requests", "active_requests"],
    ["History Count", "history_count", "int"],
    ["Created At", "created_at", "datetime"]
  ],
  "Rate Management": [
    ["Vendor", "vendor_name"],
    ["Truck Type", "truck_type_name"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["Rate/Trip", "rate_per_trip", "money"],
    ["Default Rate", "default_rate", "money"],
    ["Additional Destination Drops", "additional_drops"],
    ["Foul Trip %", "foul_trip_pct", "pct"],
    ["Fuel Surcharge %", "fuel_surcharge_pct", "pct"],
    ["Effective Date", "effective_date", "date"],
    ["Expiry Date", "expiry_date", "date"],
    ["Is Active", "is_active"],
    ["Created At", "created_at", "datetime"]
  ],
  "Vendor Speed Performance": [
    ["Request #", "request_number"],
    ["Trip ID", "trip_id"],
    ["Drop #", "drop_sequence", "int"],
    ["Distance (KM)", "distance_km", "num"],
    ["Account", "account_name"],
    ["Department", "department_name"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["International MAWB", "international_mawb"],
    ["Domestic MAWB", "domestic_mawb"],
    ["Truck Type", "truck_type_name"],
    ["Truck Plate #", "plate_number"],
    ["Vendor", "vendor_name"],
    ["Booking Date", "booking_date", "date"],
    ["Status", "status_name"],
    ["Final Call Datetime", "final_call_datetime", "datetime"],
    ["Delivered Date", "delivered_date", "date"],
    ["Customs to Arrival", "lt_customs_to_arrival"],
    ["Initial Call datetime (TBC) to Arrival", "lt_pickup_to_arrival"],
    ["Arrival to Start Load", "lt_arrival_to_start_load"],
    ["Start to End Load", "lt_start_load_to_end_load"],
    ["End Load to Arrived Dest", "lt_end_load_to_arrived_dest"],
    ["Arrived to Start Unload", "lt_arrived_dest_to_start_unload"],
    ["Start to End Unload", "lt_start_unload_to_end_unload"],
    ["Full Leg", "lt_full_leg"]
  ],
  "Cost Analysis": [
    ["Request #", "request_number"],
    ["Trip ID", "trip_id"],
    ["Account", "account_name"],
    ["Department", "department_name"],
    ["Distance (KM)", "distance_km", "num"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["International MAWB", "international_mawb"],
    ["Domestic MAWB", "domestic_mawb"],
    ["Truck Type", "truck_type_name"],
    ["Vendor", "vendor_name"],
    ["Booking Date", "booking_date", "date"],
    ["Initial Call datetime (TBC)", "call_datetime", "datetime"],
    ["Final Call Datetime", "final_call_datetime", "datetime"],
    ["Delivered Date", "delivered_date", "date"],
    ["Rate Basis", "rate_basis"],
    ["Rate Amount", "rate_amount", "money"],
    ["Actual Cost", "actual_cost", "money"],
    ["Toll Fee", "toll_fee", "money"],
    ["Management Fee", "management_fee", "money"],
    ["Fuel", "fuel", "money"],
    ["Parking", "parking", "money"],
    ["Miscellaneous", "miscellaneous", "money"],
    ["Manpower", "manpower", "money"],
    ["Toll", "toll", "money"],
    ["Welfare", "welfare", "money"],
    ["WH Rental", "wh_rental", "money"],
    ["Toll Fee (Easytrip)", "toll_fee_easytrip", "money"],
    ["Toll Fee (Autosweep)", "toll_fee_autosweep", "money"],
    ["Foul Trip Cost", "foul_trip_cost", "money"],
    ["Fuel Surcharge Cost", "fuel_surcharge_cost", "money"],
    ["Total Cost", "total_cost", "money"],
    ["Status", "status_name"],
    ["Foul Trip Date", "foul_trip_date", "date"],
    ["Foul Trip Count Confirmation", "foul_trip_count", "int"],
    ["Foul Trip Reason", "foul_trip_reason"],
    ["Updated By", "cost_updated_by_email"],
    ["Updated At", "cost_updated_at", "datetime"]
  ],
  "Foul Trip Approval": [
    ["Request #", "request_number"],
    ["Trip ID", "trip_id"],
    ["Account", "account_name"],
    ["Department", "department_name"],
    ["Distance (KM)", "distance_km", "num"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["International MAWB", "international_mawb"],
    ["Domestic MAWB", "domestic_mawb"],
    ["Truck Type", "truck_type_name"],
    ["Truck Plate #", "plate_number"],
    ["Vendor", "vendor_name"],
    ["Booking Date", "booking_date", "date"],
    ["Initial Call datetime (TBC)", "call_datetime", "datetime"],
    ["Final Call Datetime", "final_call_datetime", "datetime"],
    ["Rate Basis", "rate_basis"],
    ["Rate/Trip", "rate_per_trip", "money"],
    ["Foul Trip %", "foul_trip_pct", "pct"],
    ["Foul Trip Date", "foul_trip_date", "date"],
    ["Foul Trip Count Confirmation", "foul_trip_count", "int"],
    ["Foul Trip Cost", "foul_trip_cost", "money"],
    ["Foul Trip Reason", "foul_trip_reason"],
    ["Status", "status_name"],
    ["Approval Status", "approval_status"],
    ["Approved By", "foul_trip_approved_by_email"],
    ["Approved At", "foul_trip_approved_at", "datetime"]
  ],
  "Trip Utilisation Review": [
    ["Trip ID", "trip_id"],
    ["Final Call Datetime", "final_call_datetime", "datetime"],
    ["Status", "status_name"],
    ["Requests", "request_count", "int"],
    ["Origin Port", "origin_port_name"],
    ["Department", "department_name"],
    ["Vendor", "vendor_name"],
    ["Truck Type", "truck_type_name"],
    ["Capacity (units)", "max_capacity_units", "num"],
    ["Initial Qty (units)", "initial_units", "num"],
    ["Initial Utilisation %", "initial_utilisation", "pct"],
    ["Initial Tier", "initial_tier"],
    ["Revised Qty (units)", "revised_units", "num"],
    ["Revised Utilisation %", "revised_utilisation", "pct"],
    ["Revised Tier", "revised_tier"]
  ],
  "Ports":        [["ID", "id", "int"], ["Name", "name"], ["Code", "code"], ["Address", "location"], ["Latitude", "latitude", "num"], ["Longitude", "longitude", "num"], ["Is Active", "is_active"], ["Created At", "created_at", "datetime"]],
  "Accounts":     [["ID", "id", "int"], ["Name", "name"], ["Code", "code"], ["Is Active", "is_active"], ["Created At", "created_at", "datetime"]],
  "Departments":  [["ID", "id", "int"], ["Name", "name"], ["Code", "code"], ["Is Active", "is_active"], ["Created At", "created_at", "datetime"]],
  "Packaging":    [["ID", "id", "int"], ["Name", "name"], ["Code", "code"], ["Is Active", "is_active"], ["Created At", "created_at", "datetime"]],
  "Statuses":     [["ID", "id", "int"], ["Name", "name"], ["Color", "color"], ["Is Active", "is_active"], ["Created At", "created_at", "datetime"]],
  "Truck Types":  [["ID", "id", "int"], ["Name", "name"], ["Code", "code"], ["Max KG", "max_capacity_kg", "num"], ["Max CBM", "max_capacity_cbm", "num"], ["Max Capacity (units)", "max_capacity_units", "num"], ["Capacities", "capacities"], ["Is Active", "is_active"], ["Created At", "created_at", "datetime"]],
  "Vendors":      [["ID", "id", "int"], ["Name", "name"], ["Contact Person", "contact_person"], ["Phone", "phone"], ["Email", "email"], ["Address", "address"], ["Is Active", "is_active"], ["Created At", "created_at", "datetime"]],
  "Capacity Conversion": [
    ["Packaging Type", "packaging_type"],
    ["Code", "code"],
    ["Base Packaging Unit", "base_unit"],
    ["Is Base Unit", "is_base"],
    ["Factor (base units per 1 unit)", "factor", "num"],
    ["Inverse", "inverse", "num"]
  ]
};

// Cell number format per column type ("@" = plain text; null = Sheets' automatic
// number format, which shows 6 as 6 and 4.5 as 4.5).
var FORMATS = {
  "text": "@", "link": "@", "files": "@",
  "int": "0", "num": null, "money": "#,##0.00", "pct": "0.0",
  "date": "yyyy-mm-dd", "datetime": "yyyy-mm-dd hh:mm"
};

function headersFor(sheetName) {
  return (FIELDS[sheetName] || []).map(function(f) { return f[0]; });
}

// ============================================================
// SETUP — run once (and again after updating this script)
// ============================================================

function setupSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var def = ss.getSheetByName("Sheet1");
  SECTIONS.forEach(function(s) {
    var sh = ss.getSheetByName(s.sheet);
    if (!sh) {
      sh = ss.insertSheet(s.sheet);
    }
    var hdrs = headersFor(s.sheet);
    if (hdrs.length) {
      sh.getRange(1, 1, 1, hdrs.length).setValues([hdrs]).setFontWeight("bold");
      sh.getFrozenRows() === 0 && sh.setFrozenRows(1);
    }
  });
  if (def && def.getLastRow() === 0 && def.getLastColumn() === 0) {
    ss.deleteSheet(def);
  }
  Logger.log("Sheets setup complete.");
}

// ============================================================
// AUTO-SYNC — called by time trigger (hourly)
// ============================================================

function syncAll() {
  SECTIONS.forEach(function(s) {
    try {
      syncSection(s);
    } catch (e) {
      Logger.log("ERROR syncing " + s.sheet + ": " + e);
    }
  });
  Logger.log("Sync complete at " + new Date().toISOString());
}

function absUrl(path) {
  if (!path) return "";
  return /^https?:/i.test(path) ? path : BACKEND_URL + path;
}

// Value written into the cell for one field, according to its column type.
function cellValue(f, row) {
  var header = f[0], type = f[2] || "text", val = row[f[1]];
  if (val === undefined || val === null || val === "") return "";
  if (type === "int" || type === "num" || type === "money" || type === "pct") {
    var n = Number(val);
    return isNaN(n) ? String(val) : n;
  }
  if (type === "date" || type === "datetime") {
    var t = String(val).replace("T", " ").replace(/\.\d+/, "").replace(/Z$/, "");
    return type === "date" ? t.slice(0, 10) : t.slice(0, 19);
  }
  if (type === "files" && Array.isArray(val)) {
    return val.map(function(a) { return a.original_filename || a.filename || a.name || "file"; }).join(", ");
  }
  if (header === "Current Requests" && Array.isArray(val)) {
    return val.map(function(r) { return r.request_number || ""; }).join(", ");
  }
  if (header === "Capacities" && Array.isArray(val)) {
    return val.map(function(c) { return (c.packaging_type_name || "") + ": " + (c.max_quantity || 0); }).join("; ");
  }
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (Array.isArray(val)) return val.map(function(x) { return typeof x === "object" ? JSON.stringify(x) : String(x); }).join(", ");
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

// Rich text (clickable download links) for link / files columns; null = plain cell.
function cellLinks(f, row, text) {
  var type = f[2];
  if (type === "link") {
    var url = absUrl(row[f[3]]);
    if (!url || !text) return null;
    return SpreadsheetApp.newRichTextValue().setText(String(text)).setLinkUrl(url).build();
  }
  if (type === "files") {
    var files = row[f[1]];
    if (!Array.isArray(files) || !files.length) return null;
    var b = SpreadsheetApp.newRichTextValue().setText(String(text));
    var pos = 0;
    files.forEach(function(a, i) {
      var name = a.original_filename || a.filename || a.name || "file";
      if (a.download_url) b.setLinkUrl(pos, pos + name.length, absUrl(a.download_url));
      pos += name.length + 2;
    });
    return b.build();
  }
  return null;
}

function syncSection(section) {
  var url = BACKEND_URL + section.endpoint;
  var options = { "method": "get", "muteHttpExceptions": true, "followRedirects": true };
  var resp = UrlFetchApp.fetch(url, options);
  if (resp.getResponseCode() !== 200) {
    Logger.log("HTTP " + resp.getResponseCode() + " for " + section.endpoint);
    return;
  }
  var data = JSON.parse(resp.getContentText());
  if (!Array.isArray(data)) data = [];

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(section.sheet);
  if (!sh) {
    sh = ss.insertSheet(section.sheet);
  }

  var fields = FIELDS[section.sheet] || [];
  var hdrs = headersFor(section.sheet);
  if (!hdrs.length) return;

  // Keep the header row in line with this script (new / renamed / removed columns).
  var lastCol = Math.max(sh.getLastColumn(), hdrs.length);
  var curHdr = sh.getLastRow() > 0 ? sh.getRange(1, 1, 1, lastCol).getValues()[0] : [];
  var needsUpdate = sh.getLastColumn() > hdrs.length;
  for (var hi = 0; !needsUpdate && hi < hdrs.length; hi++) {
    if (String(curHdr[hi] || "") !== hdrs[hi]) needsUpdate = true;
  }
  if (needsUpdate) {
    if (sh.getLastColumn() > hdrs.length) {
      sh.getRange(1, hdrs.length + 1, sh.getMaxRows(), sh.getLastColumn() - hdrs.length).clear();
    }
    sh.getRange(1, 1, 1, hdrs.length).setNumberFormat("@").setValues([hdrs]).setFontWeight("bold");
    if (sh.getFrozenRows() === 0) sh.setFrozenRows(1);
    Logger.log(section.sheet + ": headers refreshed");
  }

  // Clear the old rows (values, links and leftover formats) before writing.
  if (sh.getMaxRows() > 1) {
    sh.getRange(2, 1, sh.getMaxRows() - 1, hdrs.length).clear();
  }

  if (!data.length) {
    Logger.log(section.sheet + ": cleared (no data)");
    return;
  }
  if (sh.getMaxRows() < data.length + 1) {
    sh.insertRowsAfter(sh.getMaxRows(), data.length + 1 - sh.getMaxRows());
  }

  // Set each column's format first, so e.g. 11E-00087 stays text and Drop # stays a number.
  fields.forEach(function(f, ci) {
    var fmt = FORMATS[f[2] || "text"];
    if (fmt) sh.getRange(2, ci + 1, data.length, 1).setNumberFormat(fmt);
  });

  var rows = data.map(function(row) {
    return fields.map(function(f) { return cellValue(f, row); });
  });
  sh.getRange(2, 1, rows.length, hdrs.length).setValues(rows);

  // Clickable download links.
  fields.forEach(function(f, ci) {
    if (f[2] !== "link" && f[2] !== "files") return;
    var rich = data.map(function(row, ri) {
      return [cellLinks(f, row, rows[ri][ci]) || SpreadsheetApp.newRichTextValue().setText(String(rows[ri][ci])).build()];
    });
    sh.getRange(2, ci + 1, rich.length, 1).setRichTextValues(rich);
  });

  Logger.log(section.sheet + ": synced " + rows.length + " rows");
}

// ============================================================
// TRIGGER MANAGEMENT
// ============================================================

function installTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(t) {
    if (t.getHandlerFunction() === "syncAll") {
      ScriptApp.deleteTrigger(t);
    }
  });
  ScriptApp.newTrigger("syncAll")
    .timeBased()
    .everyHours(1)
    .create();
  Logger.log("Hourly auto-sync trigger installed.");
}

function removeTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(t) {
    if (t.getHandlerFunction() === "syncAll") {
      ScriptApp.deleteTrigger(t);
    }
  });
  Logger.log("Auto-sync trigger removed.");
}

// ============================================================
// MANUAL SYNC — run from editor to test
// ============================================================

function manualSync() {
  syncAll();
}

function testConnection() {
  try {
    var resp = UrlFetchApp.fetch(BACKEND_URL + "/health", { "muteHttpExceptions": true });
    Logger.log("Health: " + resp.getResponseCode() + " " + resp.getContentText());
  } catch (e) {
    Logger.log("Connection failed: " + e);
  }
}
