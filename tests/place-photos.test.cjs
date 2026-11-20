/* scripts/place-photos-core.js: which Wikidata label counts as "the same place". Pairs from a real run of the
   photo index (NYC place lists ⇄ Wikidata labels within 150 m), reviewed by hand. */
const assert=require('node:assert/strict');
const {ppSameName,ppAuthor}=require('../scripts/place-photos-core.js');
const same=[['Anne Frank Tree','Anne Frank Tree at Liberty Park'],['MĒRCER LABS','Mercer Labs Museum of Art and Technology'],['Sunnyside Arch','Sunnyside Arch'],
 ['2 Park Avenue Building','2 Park Avenue'],['330 East 18th Street House','Houses at 326, 328 and 330 East 18th Street'],['Holyrood Episcopal Church-Iglesia Santa Cruz','Holyrood Episcopal Church'],
 ['Saint Paul\'s Chapel','St. Paul\'s Chapel'],['Waldorf-Astoria Hotel','Waldorf-Astoria Hotel (New York, N.Y.)'],['La MaMa','La MaMa Experimental Theatre Club'],
 ['Queens Library - Sunnyside Branch','Sunnyside Library'],['Rego Park Branch Queens Borough Public Library','Rego Park Library'],['Pier 97','pier 97'],
 ['Target Community Garden','Target Brooklyn Community Garden'],['Loews Regency','Loews Regency New York Hotel'],
 ['Church of St. Joseph of the Holy Family',"St. Joseph of the Holy Family's Church"],['Flatiron','Flatiron Building'],['254-260 Canal Street','254-260 Canal Street'],['Pier 57 Rooftop Park','Pier 57 rooftop park'],['32 Dominick Street House','32, 34 & 36 Dominick Street Houses'],['Apollo Theater','Apollo Theater']];
const different=[['Chelsea Savoy Hotel','Hotel Chelsea'],['Fort Tryon Park Tablet','Fort Tryon Park'],['Chelsea Piers Section Improvement','Chelsea Piers'],
 ['678 Lafayette Avenue House (Magnolia Grandiflora)','Magnolia grandiflora'],['Central Park','Central Park Zoo'],['Washington Square Park','Washington Square Arch'],
 ["St. Paul's Chapel","St. Paul's Church"],['Parsonage of the Church of the Holy Trinity','Holy Trinity Church'],
 ['Edgecombe Avenue','555 Edgecombe Avenue'],['858 West End Avenue House','840 West End Avenue'],
 ['Residence Inn New York Downtown Manhattan/World Trade Center Area','World Trade Center twin towers']];
for(const [a,b] of same)assert(ppSameName(a,b),`should match: ${a} ⇄ ${b}`);
for(const [a,b] of different)assert(!ppSameName(a,b),`must not match: ${a} ⇄ ${b}`);
assert.equal(ppAuthor('<a href="x">1_Wall_Street_001.JPG</a>'),'','a source file name is not an author');
assert.equal(ppAuthor('<a href="x">Ajay Suresh</a> from New York, NY, USA'),'Ajay Suresh');
// Artist holding a licence note or the work's maker: the Attribution field's name, else none (2026-11-20)
assert.equal(ppAuthor('You may select the license of your choice.','<a href="//commons.wikimedia.org/wiki/User:Padraic">Padraic Ryan</a>'),'Padraic Ryan');
assert.equal(ppAuthor('Sculpture by Paul Manship; I took this photograph.'),'');
assert.equal(ppAuthor('Regimus LaFort is listed as the Censor Librorum, and Cardinal John Farley is listed'),'');
console.log('place-photos: ok');
