const tabs = [...document.querySelectorAll('[role="tab"]')];
const panels = [...document.querySelectorAll('[role="tabpanel"]')];
const resultRegion = document.querySelector('#result-region');
const authPanel = document.querySelector('#auth-panel');
const authStatus = document.querySelector('#auth-status');
let auth = null;
let currentUser = null;
let authSdk = null;
let authIsRequired = false;
let appCheck = null;
let appCheckSdk = null;

function setToolsEnabled(enabled) {
  document.querySelectorAll('.task-form input, .task-form textarea, .task-form button').forEach((element) => { element.disabled = !enabled; });
}

async function initializeAuth() {
  try {
    const response = await fetch('/api/config', { cache: 'no-store' });
    const config = await response.json();
    authIsRequired = config.auth_mode === 'firebase';
    if (!authIsRequired) return;
    authPanel.hidden = false;
    setToolsEnabled(false);
    const firebase = config.firebase || {};
    if (!firebase.apiKey || !firebase.projectId || !firebase.authDomain) {
      authStatus.textContent = 'Secure sign-in is not configured. The document tools are unavailable until the deployment owner finishes Identity Platform setup.';
      return;
    }
    if (config.appCheckRequired && (!firebase.appId || !config.appCheckSiteKey)) {
      authStatus.textContent = 'App Check is not configured. Document analysis is disabled until the deployment owner finishes abuse protection setup.';
      return;
    }
    const [{ initializeApp }, authApi, checkApi] = await Promise.all([
      import('https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js'),
      import('https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js'),
      config.appCheckRequired ? import('https://www.gstatic.com/firebasejs/11.10.0/firebase-app-check.js') : Promise.resolve(null),
    ]);
    authSdk = authApi;
    const app = initializeApp(firebase);
    if (checkApi) {
      appCheckSdk = checkApi;
      appCheck = checkApi.initializeAppCheck(app, {
        provider: new checkApi.ReCaptchaEnterpriseProvider(config.appCheckSiteKey),
        isTokenAutoRefreshEnabled: true,
      });
    }
    // App Check must be initialized before any Firebase service when Auth
    // enforcement is enabled, otherwise the first Auth requests can be rejected.
    auth = authApi.getAuth(app);
    authApi.onAuthStateChanged(auth, (user) => {
      currentUser = user;
      const verified = Boolean(user?.emailVerified);
      setToolsEnabled(verified);
      document.querySelector('#auth-sign-in').hidden = Boolean(user);
      document.querySelector('#auth-sign-up').hidden = Boolean(user);
      document.querySelector('#auth-email').hidden = Boolean(user);
      document.querySelector('#auth-password').hidden = Boolean(user);
      document.querySelector('label[for="auth-email"]').hidden = Boolean(user);
      document.querySelector('label[for="auth-password"]').hidden = Boolean(user);
      document.querySelector('#auth-reset').hidden = Boolean(user);
      document.querySelector('#auth-sign-out').hidden = !user;
      document.querySelector('#auth-verify').hidden = !user || verified;
      authStatus.textContent = !user
        ? 'Sign in with a verified email account. Each account has an hourly and daily analysis allowance.'
        : verified
          ? `Signed in as ${user.email}. Document analysis is enabled.`
          : `Verify ${user.email} using the link we emailed you, then sign in again to enable document analysis.`;
    });
  } catch (_) {
    if (authPanel) {
      authPanel.hidden = false;
      authStatus.textContent = 'Secure sign-in could not be initialized. Document analysis is disabled; reload or contact the deployment owner.';
    }
    setToolsEnabled(false);
  }
}

function authErrorMessage(error) {
  const messages = {
    'auth/email-already-in-use': 'An account already exists for this email. Try signing in.',
    'auth/invalid-credential': 'Email or password was not accepted.',
    'auth/weak-password': 'Choose a password with at least 8 characters.',
    'auth/too-many-requests': 'Sign-in is temporarily blocked after repeated attempts. Try again later.',
    'auth/network-request-failed': 'The sign-in service could not be reached. Check your connection and try again.',
    'auth/operation-not-allowed': 'Email and password sign-in is disabled for this project. Contact the deployment owner.',
    'auth/unauthorized-domain': 'This site is not authorized for Firebase sign-in. Contact the deployment owner.',
    'auth/invalid-api-key': 'The sign-in service has an invalid Firebase API key. Contact the deployment owner.',
    'auth/app-not-authorized': 'This site is not authorized to use the Firebase project. Contact the deployment owner.',
    'auth/captcha-check-failed': 'The browser verification did not pass. Reload the page and try again.',
    'auth/missing-app-credential': 'Browser verification could not be completed. Reload the page and try again.',
    'auth/invalid-app-credential': 'Browser verification was rejected. Reload the page and try again.',
    'auth/app-check-token-expired': 'Browser verification expired. Reload the page and try again.',
    'auth/invalid-app-check-token': 'Browser verification was rejected. Reload the page and try again.',
  };
  return messages[error?.code] || (error?.code
    ? `Sign-in could not complete (${error.code}). Reload the page; if it continues, share this code with the deployment owner.`
    : 'The sign-in request could not be completed. Check the details and try again.');
}

document.querySelector('#auth-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!auth || !authSdk) return;
  const email = document.querySelector('#auth-email').value.trim();
  const password = document.querySelector('#auth-password').value;
  try {
    await authSdk.signInWithEmailAndPassword(auth, email, password);
  } catch (error) { authStatus.textContent = authErrorMessage(error); }
});

document.querySelector('#auth-sign-up').addEventListener('click', async () => {
  if (!auth || !authSdk) return;
  const email = document.querySelector('#auth-email').value.trim();
  const password = document.querySelector('#auth-password').value;
  if (!email || password.length < 8) { authStatus.textContent = 'Enter an email and a password with at least 8 characters.'; return; }
  try {
    const result = await authSdk.createUserWithEmailAndPassword(auth, email, password);
    await authSdk.sendEmailVerification(result.user);
    authStatus.textContent = `We sent a verification link to ${email}. Open it, then sign in again.`;
    await authSdk.signOut(auth);
  } catch (error) { authStatus.textContent = authErrorMessage(error); }
});

document.querySelector('#auth-reset').addEventListener('click', async () => {
  if (!auth || !authSdk) return;
  const email = document.querySelector('#auth-email').value.trim();
  if (!email) { authStatus.textContent = 'Enter your email address first.'; return; }
  try {
    await authSdk.sendPasswordResetEmail(auth, email);
    authStatus.textContent = 'If an account exists for that email, a password reset link has been sent.';
  } catch (_) { authStatus.textContent = 'The password reset request could not be completed. Try again later.'; }
});

document.querySelector('#auth-verify').addEventListener('click', async () => {
  if (!currentUser || !authSdk) return;
  try {
    await authSdk.sendEmailVerification(currentUser);
    authStatus.textContent = `A new verification link was sent to ${currentUser.email}.`;
  } catch (_) { authStatus.textContent = 'A verification email could not be sent just now. Try again later.'; }
});

document.querySelector('#auth-sign-out').addEventListener('click', async () => {
  if (auth && authSdk) await authSdk.signOut(auth);
});

initializeAuth();

tabs.forEach((tab, index) => { tab.tabIndex = index === 0 ? 0 : -1; });

tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => activateTab(tab));
  tab.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    activateTab(tabs[next]);
    tabs[next].focus();
  });
});

function activateTab(tab) {
  tabs.forEach((item) => {
    const active = item === tab;
    item.classList.toggle('active', active);
    item.setAttribute('aria-selected', String(active));
    item.tabIndex = active ? 0 : -1;
  });
  panels.forEach((panel) => { panel.hidden = panel.id !== tab.getAttribute('aria-controls'); });
}

for (const id of ['brief-file', 'ask-file', 'before-file', 'after-file']) {
  const input = document.getElementById(id);
  input.addEventListener('change', () => {
    const target = document.getElementById(`${id.replace('-file', '')}-file-name`);
    if (target) target.textContent = input.files[0]?.name || 'Choose a PDF';
  });
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function citationBlock(citation) {
  const block = node('blockquote', 'citation');
  block.append(node('strong', '', `${citation.document} · page ${citation.page}`));
  block.append(node('q', '', citation.quote));
  return block;
}

function resultShell(title, status) {
  const card = node('article', 'result-card');
  const header = node('div', 'result-header');
  header.append(node('span', 'result-dot'));
  header.append(node('h2', '', title));
  header.append(node('span', `status-pill ${status}`, status.replaceAll('_', ' ')));
  card.append(header);
  return card;
}

function renderBrief(data) {
  const card = resultShell('Your document briefing', data.status);
  card.append(node('p', 'overview', data.overview));
  data.overview_citations.forEach((citation) => card.append(citationBlock(citation)));
  for (const finding of data.key_points) {
    const section = node('section', 'finding');
    section.append(node('h3', '', finding.topic));
    section.append(node('p', 'result-copy', finding.explanation));
    if (finding.uncertainty) section.append(node('p', 'result-copy', `Needs clarification: ${finding.uncertainty}`));
    finding.citations.forEach((citation) => section.append(citationBlock(citation)));
    card.append(section);
  }
  if (data.verify_with_professional.length) {
    card.append(node('h3', '', 'Questions to consider asking a professional'));
    const list = node('ul', 'result-list');
    data.verify_with_professional.forEach((item) => list.append(node('li', '', item)));
    card.append(list);
  }
  if (data.limitations.length) data.limitations.forEach((item) => card.append(node('p', 'result-copy', item)));
  return card;
}

function renderAnswer(data) {
  const card = resultShell('Answer from the document', data.status);
  card.append(node('p', 'overview', data.answer));
  data.citations.forEach((citation) => card.append(citationBlock(citation)));
  for (const uncertainty of data.uncertainties) card.append(node('p', 'result-copy', `Uncertainty: ${uncertainty}`));
  if (data.questions_for_professional.length) {
    card.append(node('h3', '', 'Questions to consider asking a professional'));
    const list = node('ul', 'result-list');
    data.questions_for_professional.forEach((item) => list.append(node('li', '', item)));
    card.append(list);
  }
  return card;
}

function renderCompare(data) {
  const card = resultShell('What changed', data.status);
  card.append(node('p', 'result-copy', data.overall_note));
  for (const change of data.changes) {
    const item = node('article', 'change-card');
    item.append(node('span', 'change-type', change.change_type.replaceAll('_', ' ')));
    item.append(node('h3', '', change.topic));
    const columns = node('div', 'change-columns');
    columns.append(node('div', 'change-side', `Earlier version\n${change.before || 'No corresponding text'}`));
    columns.append(node('div', 'change-side', `Later version\n${change.after || 'No corresponding text'}`));
    item.append(columns);
    item.append(node('p', 'result-copy', change.explanation));
    change.citations.forEach((citation) => item.append(citationBlock(citation)));
    card.append(item);
  }
  if (data.verify_with_professional.length) {
    const list = node('ul', 'result-list');
    data.verify_with_professional.forEach((item) => list.append(node('li', '', item)));
    card.append(list);
  }
  return card;
}

async function submit(form, button, endpoint, formData, render) {
  resultRegion.replaceChildren(node('div', 'loading', 'Reading the document and preparing a source-grounded response…'));
  button.disabled = true;
  button.dataset.originalText = button.textContent;
  button.textContent = 'Working…';
  try {
    const headers = {};
    if (authIsRequired) {
      if (!currentUser || !currentUser.emailVerified) throw new Error('Sign in with a verified email account before analyzing a document.');
      headers.Authorization = `Bearer ${await currentUser.getIdToken(true)}`;
      if (appCheck && appCheckSdk) {
        const attestation = await appCheckSdk.getToken(appCheck, true);
        headers['X-Firebase-AppCheck'] = attestation.token;
      }
    }
    const response = await fetch(endpoint, { method: 'POST', headers, body: formData, credentials: 'same-origin' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'The request could not be completed.');
    resultRegion.replaceChildren(render(data));
    resultRegion.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    resultRegion.replaceChildren(node('div', 'error', error.message || 'Something went wrong. Please try again.'));
  } finally {
    button.disabled = false;
    button.textContent = button.dataset.originalText || 'Try again';
  }
}

document.querySelector('#brief-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  submit(form, form.querySelector('button[type="submit"]'), '/api/briefing', new FormData(form), renderBrief);
});

document.querySelector('#ask-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  submit(form, form.querySelector('button[type="submit"]'), '/api/answer', new FormData(form), renderAnswer);
});

document.querySelector('#compare-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const data = new FormData();
  data.append('before_file', document.querySelector('#before-file').files[0]);
  data.append('after_file', document.querySelector('#after-file').files[0]);
  data.append('lens', document.querySelector('#lens').value);
  const form = event.currentTarget;
  submit(form, form.querySelector('button[type="submit"]'), '/api/compare', data, renderCompare);
});
