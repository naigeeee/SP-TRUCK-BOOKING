// ============================================================
// One-off import: old "CENTRALIZED TRUCK BOOKING" sheet -> this sheet
// ============================================================
// Reads the old sheet's MASTERLIST tab and writes every trip (VSP#####) into the
// tab "Imported (Centralized Truck Booking)" using the Masterlist column layout,
// plus a few "Source: ..." columns at the end for details that have no home there.
// The hourly app sync never touches this tab. Run importCentralizedTruckBooking()
// again at any time to refresh it from the old sheet (the tab is rewritten).

var IMPORT_SOURCE_ID = "1RHQgbhF49aUyAFIpJF_kOhdKqoXuHRosNJ1iN4nZfNc";
var IMPORT_SOURCE_TAB = "MASTERLIST";
var IMPORT_TARGET_TAB = "Imported (Centralized Truck Booking)";

var IMPORT_HEADERS = ["Request #", "Requestor Name", "Requestor Email", "Manifest", "Pickup Scan Manifest",
  "Unloading Scan Manifest", "Status", "Account", "Department", "Origin Port", "Destination Port",
  "International MAWB", "Domestic MAWB", "Truck Type", "Truck Plate #", "Packaging", "Initial Qty",
  "Revised Qty", "Vendor", "Final Call Datetime", "Trip ID", "Driver", "Driver Name", "Driver Phone",
  "Drop #", "Distance (KM)", "Booking Date", "Initial Call datetime (TBC)", "Customs Cleared",
  "Instructions", "Arrived Pickup", "Late Reason", "Start Loading", "End Loading", "Arrived Destination",
  "Start Unloading", "End Unloading", "Unloading Remarks", "Delivered Date", "Foul Trip Reason",
  "Foul Trip Date", "Foul Trip Count Confirmation", "Foul Trip Approval", "Cancellation Date", "Consol",
  "Attachments", "Updated By", "Updated By Email", "Updated At", "Created At",
  "Source: SP Status", "Source: Vendor Status", "Source: Helper", "Source: Fault Liable",
  "Source: Foul Trip Occurred", "Source: Duration Pick-up", "Source: Duration Destination",
  "Source: CT Performance", "Source: Trip Duration"];

var IMP_MON = {jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12};

function impDate_(s) {
  var m = String(s || "").trim().match(/^(\d{1,2})-([A-Za-z]{3})-(\d{4})$/);
  if (!m || !IMP_MON[m[2].toLowerCase()]) return null;
  return Date.UTC(+m[3], IMP_MON[m[2].toLowerCase()] - 1, +m[1]);
}
// Minutes after midnight; tolerates typos like "03;00", "11:00." Returns null when unreadable.
function impTime_(s) {
  s = String(s || "").trim();
  if (!s) return null;
  var t = s.replace(/;/g, ":").replace(/\.$/, "").replace(/\.(?=\d)/, ":");
  var m = t.match(/^(\d{1,2}):(\d{2})(?::\d{2})?$/);
  if (m && +m[1] < 24 && +m[2] < 60) return (+m[1]) * 60 + (+m[2]);
  return null;
}
function impP2_(n) { return (n < 10 ? "0" : "") + n; }
function impFd_(ms) {
  if (ms == null) return "";
  var x = new Date(ms);
  return x.getUTCFullYear() + "-" + impP2_(x.getUTCMonth() + 1) + "-" + impP2_(x.getUTCDate());
}
function impFdt_(base, min) {
  if (base == null || min == null) return "";
  var x = new Date(base + min * 60000);
  return impFd_(x.getTime()) + " " + impP2_(x.getUTCHours()) + ":" + impP2_(x.getUTCMinutes());
}
function impStatus_(sp, vs) {
  sp = String(sp || "").trim().toLowerCase(); vs = String(vs || "").trim().toLowerCase();
  if (sp.indexOf("cancel") === 0) return "Cancelled";
  if (sp === "foultrip" || /foul/.test(vs)) return "Foul Trip";
  if (/delivered/.test(vs)) return "Delivered";
  if (/cancel/.test(vs)) return "Cancelled";
  if (/picked up|departed|arrived/.test(vs)) return "In Transit";
  if (sp === "confirmed booking") return "Allocated";
  return "Pending";
}

function importCentralizedTruckBooking() {
  var src = SpreadsheetApp.openById(IMPORT_SOURCE_ID).getSheetByName(IMPORT_SOURCE_TAB);
  if (!src) throw new Error("Tab " + IMPORT_SOURCE_TAB + " not found in the old sheet");
  var vals = src.getRange(1, 1, src.getLastRow(), Math.max(40, src.getLastColumn())).getDisplayValues();
  var out = [IMPORT_HEADERS], unreadable = 0;
  for (var k = 2; k < vals.length; k++) {
    var r = vals[k];
    if (!/^VSP/i.test(String(r[0] || "").trim())) continue;
    var g = function(i) { return String(r[i] == null ? "" : r[i]).replace(/[\t\r\n]+/g, " ").trim(); };
    var bd = impDate_(r[1]), td = impDate_(r[18]); if (td == null) td = bd;
    var st = impStatus_(r[14], r[30]);
    var prev = null, add = 0;
    var ms = [24, 25, 26, 27, 28, 29].map(function(i) {
      var m = impTime_(r[i]);
      if (m == null) { if (g(i)) unreadable++; return ""; }
      var v = m + add;
      if (prev != null && v < prev) { add += 1440; v += 1440; }   // passed midnight
      prev = v;
      return impFdt_(td, v);
    });
    var fc = impTime_(r[13]), ic = impTime_(r[8]);
    if (fc == null && g(13)) unreadable++;
    if (ic == null && g(8)) unreadable++;
    var vt = g(21).toUpperCase() === "CANCELLED" ? "" : g(21);
    var foul = [g(16), g(33)].filter(function(x, i, a) { return x && x.toUpperCase() !== "N/A" && a.indexOf(x) === i; }).join("; ");
    var delivered = st === "Delivered" || (st === "Foul Trip" && /delivered/i.test(r[30]));
    var row = [g(0), "", "", "", "", "", st, g(4), g(2), g(10), g(11), g(3), "", vt, g(20), g(7), g(6), "",
      g(12), impFdt_(td, fc), g(19) || g(9), "", g(22), "", "", "", impFd_(bd), impFdt_(bd, ic), "",
      [g(5), g(15)].filter(String).join(" | "),
      ms[0], "", ms[1], ms[2], ms[3], ms[4], ms[5], g(31),
      delivered ? (ms[5] ? ms[5].slice(0, 10) : impFd_(td)) : "",
      foul, st === "Foul Trip" ? impFd_(td) : "", "", "", "", g(9), "", "", "", "", "",
      g(14), g(30), g(23), g(17), g(32), g(34), g(35), g(38), g(39)];
    out.push(row.map(function(v) { return /^[=+@]/.test(v) || /^-[^\d]/.test(v) ? "'" + v : v; }));
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(IMPORT_TARGET_TAB) || ss.insertSheet(IMPORT_TARGET_TAB);
  sh.clear();
  var cols = IMPORT_HEADERS.length;
  if (sh.getMaxColumns() < cols) sh.insertColumnsAfter(sh.getMaxColumns(), cols - sh.getMaxColumns());
  if (sh.getMaxRows() < out.length) sh.insertRowsAfter(sh.getMaxRows(), out.length - sh.getMaxRows());
  for (var i = 0; i < out.length; i += 3000) {
    var part = out.slice(i, i + 3000);
    sh.getRange(i + 1, 1, part.length, cols).setValues(part);
    SpreadsheetApp.flush();
  }
  sh.getRange(1, 1, 1, cols).setFontWeight("bold");
  sh.setFrozenRows(1);
  Logger.log("Imported " + (out.length - 1) + " trips into '" + IMPORT_TARGET_TAB + "' (" + unreadable + " time cells unreadable, left blank)");
}
