package com.jawaadalah.runjumversipremium

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.max
import kotlin.math.min
import kotlin.random.Random

class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(GameView(this))
    }

    private class GameView(context: Context, attrs: AttributeSet? = null) : View(context, attrs) {

        // Game constants
        private val PLAYER_RADIUS = 50f
        private val PLAYER_X = 200f
        private val GROUND_Y = 800f
        private val GRAVITY = 1.2f
        private val JUMP_VELOCITY = -25f
        private val OBSTACLE_WIDTH = 80f
        private val OBSTACLE_HEIGHT = 200f
        private val OBSTACLE_SPEED = 12f
        private val OBSTACLE_SPAWN_INTERVAL = 1500L // ms
        private val TOTAL_TIME_MS = 30_000L // 30 seconds

        // Paints
        private val paintPlayer = Paint().apply { color = Color.BLUE }
        private val paintObstacle = Paint().apply { color = Color.RED }
        private val paintText = Paint().apply {
            color = Color.BLACK
            textSize = 64f
            isAntiAlias = true
        }
        private val paintBackground = Paint().apply { color = Color.WHITE }

        // Game state
        private enum class State { RUNNING, GAME_OVER }

        private var state = State.RUNNING

        // Player variables
        private var playerY = GROUND_Y
        private var playerVy = 0f

        // Obstacles
        private data class Obstacle(var x: Float, var y: Float, val width: Float, val height: Float)
        private val obstacles = mutableListOf<Obstacle>()
        private var lastObstacleSpawn = System.currentTimeMillis()

        // Score and timer
        private var score = 0
        private var startTime = System.currentTimeMillis()
        private var elapsedTime = 0L
        private var remainingTime = TOTAL_TIME_MS

        init {
            // Ensure view receives touch events
            isFocusable = true
            isClickable = true
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            if (event.action == MotionEvent.ACTION_DOWN) {
                when (state) {
                    State.RUNNING -> {
                        if (playerY >= GROUND_Y) {
                            playerVy = JUMP_VELOCITY
                        }
                    }
                    State.GAME_OVER -> {
                        restartGame()
                    }
                }
                return true
            }
            return super.onTouchEvent(event)
        }

        private fun restartGame() {
            state = State.RUNNING
            playerY = GROUND_Y
            playerVy = 0f
            obstacles.clear()
            lastObstacleSpawn = System.currentTimeMillis()
            score = 0
            startTime = System.currentTimeMillis()
            elapsedTime = 0L
            remainingTime = TOTAL_TIME_MS
        }

        override fun onDraw(canvas: Canvas) {
            // Background
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paintBackground)

            if (state == State.RUNNING) {
                val now = System.currentTimeMillis()
                // Update timer
                elapsedTime = now - startTime
                remainingTime = max(0L, TOTAL_TIME_MS - elapsedTime)
                if (remainingTime == 0L) {
                    state = State.GAME_OVER
                }

                // Update player
                playerVy += GRAVITY
                playerY += playerVy
                if (playerY > GROUND_Y) {
                    playerY = GROUND_Y
                    playerVy = 0f
                }

                // Draw player (custom skin: circle with gradient color could be added)
                canvas.drawCircle(PLAYER_X, playerY, PLAYER_RADIUS, paintPlayer)

                // Spawn obstacles
                if (now - lastObstacleSpawn >= OBSTACLE_SPAWN_INTERVAL) {
                    val obstacleY = GROUND_Y - OBSTACLE_HEIGHT
                    obstacles.add(Obstacle(width.toFloat(), obstacleY, OBSTACLE_WIDTH, OBSTACLE_HEIGHT))
                    lastObstacleSpawn = now
                }

                // Update and draw obstacles
                val iterator = obstacles.iterator()
                while (iterator.hasNext()) {
                    val obs = iterator.next()
                    obs.x -= OBSTACLE_SPEED
                    if (obs.x + obs.width < 0) {
                        iterator.remove()
                        score += 1
                        continue
                    }
                    val rect = RectF(obs.x, obs.y, obs.x + obs.width, obs.y + obs.height)
                    canvas.drawRect(rect, paintObstacle)

                    // Collision detection
                    val playerRect = RectF(
                        PLAYER_X - PLAYER_RADIUS,
                        playerY - PLAYER_RADIUS,
                        PLAYER_X + PLAYER_RADIUS,
                        playerY + PLAYER_RADIUS
                    )
                    if (RectF.intersects(rect, playerRect)) {
                        state = State.GAME_OVER
                    }
                }

                // Draw score and timer
                canvas.drawText("Score: $score", 30f, 80f, paintText)
                val seconds = remainingTime / 1000
                val millis = (remainingTime % 1000) / 10
                canvas.drawText("Time: $seconds.${if (millis < 10) "0$millis" else "$millis"}", 30f, 160f, paintText)
            } else {
                // Game over screen
                canvas.drawText("Game Over", width / 2f - 180f, height / 2f - 40f, paintText)
                canvas.drawText("Score: $score", width / 2f - 150f, height / 2f + 40f, paintText)
                canvas.drawText("Tap to Restart", width / 2f - 210f, height / 2f + 120f, paintText)
            }

            // Loop
            postInvalidateDelayed(16)
        }
    }
}