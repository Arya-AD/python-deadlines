(function () {
	function displaySearchResults(results, store) {
		var searchResults = document.getElementById('search-results');

		if (results.length) {
			// Are there any results?
			var appendString = '';

			for (var i = 0; i < results.length; i++) {
				// Iterate over the results
				var item = store[results[i].ref];

				appendString += `
            <div id="${results[i].ref}" class="ConfItem ${item.subs
					.split(',')
					.map((sub) => sub.trim() + '-conf')
					.join(' ')}">
                <div class="row conf-row">
                    <div class="col-6">
                        <span class="conf-title">
                            <a title="Deadline Details" href="${item.url}">${item.title}</a>
                        </span>
                        <span class="conf-title-small">
                            <a title="Deadline Details" href="${item.url}">${item.title}</a>
                        </span>
                        ${
							item.link
								? `<span class="conf-title-icon">
                            <a title="Conference Website" href="${item.link}" target="_blank"><img src="/static/img/203-earth.svg" class="badge-link" alt="Link to Conference Website" width="16" height="16" /></a>
                            &ZeroWidthSpace;
                        </span>`
								: ''
						}
                    </div>
                </div>
                <div class="row">
                    <div class="col-12 col-sm-6">
                        <div class="meta">
                            <span class="conf-place">
                                ${item.content.length > 150 ? item.content.substring(0, 150) + '... ' : item.content},
								${
									item.place === 'Online'
										? `<a href="#">${item.place}</a>`
										: `<a href="http://maps.google.com/?q=${item.place}">${item.place}</a>`
								}
                            </span>
                        </div>
                    </div>
                    <div class="col-12 col-sm-6">
                        <div class="deadline">
                            <div>
                                <span class="deadline-time">${item.date}</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-6">
                        ${item.subs
							.split(',')
							.map(
								(sub) => `
                        <span
                            title="Click to only show ${sub.trim()} conferences"
                            data-sub="${sub.trim()}"
                            class="badge badge-light conf-sub ${sub.trim()}-tag"
                        ></span>`
							)
							.join('')}
                    </div>
                    <div class="col-6">
                        <div class="calendar"></div>
                    </div>
                </div>
                <hr />
            </div>
        `;
			}

			searchResults.innerHTML = appendString;
		} else {
			searchResults.innerHTML = '<li>No results found</li>';
		}
	}

	function getQueryVariable(variable) {
		var query = window.location.search.substring(1);
		var vars = query.split('&');

		for (var i = 0; i < vars.length; i++) {
			var pair = vars[i].split('=');

			if (pair[0] === variable) {
				return decodeURIComponent(pair[1].replace(/\+/g, '%20'));
			}
		}
	}

	var searchTerm = getQueryVariable('query');

	if (searchTerm) {
		document.getElementById('search-box').setAttribute('value', searchTerm);

		// Initalize lunr with the fields it will be searching on. I've given title
		// a boost of 10 to indicate matches on this field are more important.
		var idx = lunr(function () {
			this.field('id');
			this.field('title', { boost: 10 });
			this.field('date');
			this.field('content');

			for (var key in window.store) {
				// Add the data to lunr
				this.add({
					id: key,
					title: window.store[key].title,
					date: window.store[key].date,
					content: window.store[key].content,
				});
			}
		});

		var results = idx.search(searchTerm + '^30 *' + searchTerm + '*'); // Get lunr to perform a search
		displaySearchResults(results, window.store);
	}
})();
