import re
html=open('index.html').read()

# CSS
html=html.replace('.deck-card.core .btn-deck:hover{border-color:var(--emerald);color:var(--emerald);}',
  '.deck-card.core .btn-deck:hover{border-color:var(--emerald);color:var(--emerald);}\n.deck-card.daily_review::before{background:linear-gradient(90deg,#0ea5e9,#6366f1);}\n.deck-card.daily_review .deck-icon{background:rgba(14,165,233,.12);}\n.deck-card.daily_review .btn-deck:hover{border-color:#0ea5e9;color:#0ea5e9;}',1)

# Deck card (before hy)
DR_CARD='''      <div class="deck-card daily_review" onclick="openApp('daily_review')">
        <div class="deck-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="color:#0ea5e9"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>
        <div class="deck-name">Step 2 CK · Daily Review</div><div class="deck-title">Daily Review Cards</div>
        <div class="deck-desc">High-yield Step 2 CK flashcards for daily review.</div>
        <div class="deck-tags"><span class="deck-tag">High-Yield</span><span class="deck-tag">Daily</span><span class="deck-tag">Step 2 CK</span></div>
        <div class="deck-footer"><div class="deck-count"><strong>—</strong> <span>cards</span></div><button class="btn-deck" onclick="event.stopPropagation();this.closest('[onclick]').onclick()">Study now →</button></div>
      </div>
'''
HY='      <div class="deck-card s2" onclick="openApp(\'hy\')">'
html=html.replace(HY,DR_CARD+HY,1)

# Deck row (after core)
DR_ROW='''
        <div class="deck-row" onclick="switchDeckAndStudy('daily_review')" style="cursor:pointer">
          <div class="deck-icon" style="background:rgba(14,165,233,.1);">
            <svg viewBox="0 0 24 24" stroke="#0ea5e9"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          </div>
          <div class="deck-info"><div class="deck-title">Daily Review</div><div class="deck-sub">Step 2 CK · Daily Cards</div><div class="deck-stats-line" id="stats-daily_review"><span class="ds-total">— cards</span></div></div>
          <div class="deck-badges"></div>
          <button class="study-btn" onclick="event.stopPropagation();switchDeckAndStudy('daily_review')">Study</button>
        </div>'''
CORE_END="switchDeckAndStudy('core')\">Study</button>\n        </div>"
html=html.replace(CORE_END,CORE_END+DR_ROW,1)

open('index.html','w').write(html)
print('OK',"openApp('daily_review')" in html,"switchDeckAndStudy('daily_review')" in html)
