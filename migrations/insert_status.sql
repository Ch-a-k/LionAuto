INSERT INTO status (slug, name, hex, letter, description)
            VALUES
                ('run_&_drive', 'Run & Drive', '#15b01a', 'R', ''),
                ('unknown', 'Unknown', '#FFA500', 'U', ''),
                ('stationary', 'Stationary', '#ADD8E6', 'S', ''),
                ('starts', 'Starts', '#00008B', 'S', '')
            ON CONFLICT (slug) DO NOTHING;