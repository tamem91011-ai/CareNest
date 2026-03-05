const SUPABASE_URL = "https://pwxxdsmnqjodarkrueud.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3eHhkc21ucWpvZGFya3J1ZXVkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAwODQxOTYsImV4cCI6MjA4NTY2MDE5Nn0.gH6LJB94gxc2Et3fPEmbf6OoudYL9wSw1LgU03wLM0c";

const supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

async function signUpUser(email, password, fullName, role) {
    console.log("CareNest: Initiating registration for", email);

    const { data, error } = await supabaseClient.auth.signUp({
        email: email,
        password: password,
        options: {
            data: {
                full_name: fullName,
                care_role: role
            }
        }
    });

    if (error) {
        console.error("Auth Error:", error.message);
        alert("Registration Failed: " + error.message);
        return;
    }

    if (data.user) {
        console.log("Registration Successful! Creating profile...");

        // Create public profile entry for Phase 8 Handover features
        await supabaseClient
            .from('profiles')
            .upsert({
                id: data.user.id,
                full_name: fullName,
                care_role: role
            });

        window.location.href = 'dashboard.html';
    }
}

async function signInUser(email, password) {
    console.log("CareNest: Attempting login for", email);

    const { data, error } = await supabaseClient.auth.signInWithPassword({
        email: email,
        password: password
    });

    if (error) {
        console.error("Login Error:", error.message);
        alert("Login Failed: " + error.message);
        return;
    }

    if (data.user) {
        console.log("Login Successful!");
        window.location.href = 'dashboard.html';
    }
}

async function fetchDashboardData() {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return;

    console.log("CareNest: Fetching data for", user.email);

    const { data: meds, error: medError } = await supabaseClient
        .from('medications')
        .select('*')
        .order('pill_name', { ascending: true });

    const { data: symptoms, error: sympError } = await supabaseClient
        .from('symptom_logs')
        .select('*')
        .order('logged_at', { ascending: false });

    return { meds, symptoms };
}

async function addMedication(name, dose, freq, stock) {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return;

    console.log("CareNest: Submitting new record for", user.email);

    const { data, error } = await supabaseClient
        .from('medications')
        .insert([
            {
                user_id: user.id,
                pill_name: name,
                dosage: dose,
                frequency: freq,
                stock_count: stock
            }
        ]);

    if (error) {
        console.error("Submission Error:", error.message);
        alert("Error saving record: " + error.message);
        return;
    }

    console.log("Record Saved Successfully!");
    return data;
}

async function saveSymptom(category, observation, severity = 0, notes = "") {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return;

    const { data, error } = await supabaseClient
        .from('symptom_logs')
        .insert([{
            user_id: user.id,
            category: category,
            observation: observation,
            severity: severity,
            additional_notes: notes
        }]);

    if (error) throw error;
    return data;
}

/**
 * Step 22: Handover Documentation (Phase 8: Role-Based Feed)
 */
async function saveHandover(content) {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return;

    // Fetch sender profile for identity
    const { data: profile } = await supabaseClient
        .from('profiles')
        .select('full_name, care_role')
        .eq('id', user.id)
        .single();

    const { data, error } = await supabaseClient
        .from('handover_notes')
        .insert([{
            user_id: user.id,
            note_content: content,
            sender_name: profile ? profile.full_name : 'Staff Member',
            sender_role: profile ? profile.care_role : 'Staff'
        }]);

    if (error) throw error;
    return data;
}

async function fetchHandoverHistory() {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return [];

    const { data, error } = await supabaseClient
        .from('handover_notes')
        .select('*')
        .order('logged_at', { ascending: false })
        .limit(10); // Show last 10 for the feed

    return data || [];
}

/**
 * Step 23: Care Routine Synchronization (Phase 12: Daily Logic)
 */
async function updateRoutine(taskName, isDone, logDate = null) {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return;

    // Default to local date string (YYYY-MM-DD) if no date provided
    const targetDate = logDate || new Date().toISOString().split('T')[0];

    try {
        const { data, error } = await supabaseClient
            .from('routines')
            .upsert({
                user_id: user.id,
                task_name: taskName,
                is_completed: isDone,
                log_date: targetDate,
                updated_at: new Date().toISOString()
            }, { onConflict: 'user_id, task_name, log_date' });

        if (error) {
            console.error("Supabase Upsert Error:", error);
            // Fallback: If the log_date column (42703) or constraint (42P10) is missing
            if (error.code === '42703' || error.code === '42P10') {
                console.warn("SQL Patch (Phase 12) missing. Falling back to legacy schema.");
                const { data: fbData, error: fbError } = await supabaseClient
                    .from('routines')
                    .upsert({
                        user_id: user.id,
                        task_name: taskName,
                        is_completed: isDone,
                        updated_at: new Date().toISOString()
                    }, { onConflict: 'user_id, task_name' });

                if (!fbError) return fbData;
            }
            throw error;
        }
        return data;
    } catch (err) {
        console.error("Critical Routine Sync Failure:", err);
        // Extract exact message for UI
        err.userMessage = err.message || "Unknown Database Error";
        throw err;
    }
}
/**
 * Step 24: State Retrieval
 */
async function fetchRoutines(logDate = null) {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return [];

    const targetDate = logDate || new Date().toISOString().split('T')[0];

    const { data, error } = await supabaseClient
        .from('routines')
        .select('*')
        .eq('user_id', user.id)
        .eq('log_date', targetDate);

    if (error && error.code === '42703') {
        console.warn("SQL Patch missing. Loading legacy routines.");
        const { data: legacyData } = await supabaseClient.from('routines').select('*');
        return legacyData || [];
    }

    return data || [];
}
async function fetchRoutinePerformance() {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return [];
    const { data, error } = await supabaseClient
        .from('routines')
        .select('log_date, is_completed')
        .eq('user_id', user.id)
        .order('log_date', { ascending: false })
        .limit(200);

    if (error) {
        console.error("History Fetch Error:", error);
        return [];
    }
    if (!data || data.length === 0) return [];
    const dailyStats = data.reduce((acc, current) => {
        const d = current.log_date || new Date().toISOString().split('T')[0];
        if (!acc[d]) acc[d] = { total: 0, done: 0 };
        acc[d].total++;
        if (current.is_completed) acc[d].done++;
        return acc;
    }, {});
    const TOTAL_DAILY_TASKS = 5; // Matches the 5 clinical tasks in the UI
    return Object.keys(dailyStats)
        .map(date => ({
            date,
            percentage: Math.min(100, Math.round((dailyStats[date].done / TOTAL_DAILY_TASKS) * 100))
        }))
        .sort((a, b) => new Date(a.date) - new Date(b.date))
        .slice(-7); // Keep the last 7 active days
}

async function fetchLatestHandover() {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return null;
    const { data, error } = await supabaseClient
        .from('handover_notes')
        .select('*')
        .order('logged_at', { ascending: false })
        .limit(1);
    return data && data.length > 0 ? data[0] : null;
}

/**
 * Step 19: OpenAI Clinical Insight Bridge
 * Communicates with the Flask Python backend for AI pattern recognition.
 */
async function getAIInsight(customPrompt = null) {
    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) return null;

    try {
        const response = await fetch('http://127.0.0.1:5000/api/ai-insight', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                prompt: customPrompt
            })
        });
        const data = await response.json();
        return data;
    } catch (err) {
        console.warn("AI Backend not reachable. Ensure server.py is running!");
        return null;
    }
}


