package com.jawaadalah.youragentinisiapa

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.LinearLayout
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private var hitungan = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val label = TextView(this).apply {
            text = "Halo dari your agent ini siapa! Tombol ditekan 0 kali."
            textSize = 18f
        }
        val tombol = Button(this).apply {
            text = "Tekan saya"
            setOnClickListener {
                hitungan++
                label.text = "Halo dari your agent ini siapa! Tombol ditekan $hitungan kali."
            }
        }
        layout.addView(label)
        layout.addView(tombol)
        setContentView(layout)
    }
}
