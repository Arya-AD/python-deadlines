// Get subjects from URL/Cache
var url = new URL(window.location);
subs = url.searchParams.get('sub');
if (subs == undefined) {
  data = store.get('{{site.domain}}-subs');
  if (!data || typeof data !== 'object' || isDataExpired(data)) {
    data = { subs: data.all_subs };
  }
	subs = data.subs;
} else {
	subs = subs.toUpperCase().split(',');
}

// Apply selections
if (subs == undefined) {
	subs = all_subs;
}
$('#subject-select').multiselect('select', subs);
update_filtering({ subs: subs, all_subs: all_subs });
