// Per-site settings for the accounts UI (auth.js, history.js).
window.ARTERION_APP = {
  slug: "arrhythmia",
  name: "Arterion ECG Monitor",
  home: "index.html",
  tasks: {
    "arrhythmia": "ECG rhythm analysis"
  },
  // One-line summary of a saved result, shown at the top of its details.
  headline: function (r) {
    var n = r.beats ? r.beats.length : null;
    return (r.rhythm_type || 'Rhythm') + (r.heart_rate_bpm ? ', ' + r.heart_rate_bpm + ' bpm' : '') + (n ? ', ' + n + ' beats' : '');
  },
};
